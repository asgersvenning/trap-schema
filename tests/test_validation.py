import csv
import json
import shutil
import warnings
from pathlib import Path

import pytest
from frictionless import FrictionlessException, Report, validate
from pydantic import ValidationError

from trap_schema import DataPackage, Dataset, DeploymentsTable, MediaTable, ObservationsTable

from .helpers import DATAPACKAGE_URL, DEPLOYMENTS_URL, MEDIA_URL, OBSERVATIONS_URL, datapackage_data, table_content

pytestmark = [
    # Ignore invalid JSON in upstream example data (see https://github.com/tdwg/camtrap-dp/issues/463)
    pytest.mark.filterwarnings("ignore:Provided JSON string is not valid:UserWarning"),
    # Ignore jsonschema remote reference deprecation triggered by frictionless
    pytest.mark.filterwarnings("ignore:.*Automatically retrieving remote references.*:DeprecationWarning")
]

@pytest.fixture(scope="module")
def master_dataset_dir(tmp_path_factory) -> Path:
    """Fetches and saves the pristine dataset exactly once per test session."""
    master_tmp = tmp_path_factory.mktemp("camtrap_dp_master")
    
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Provided JSON string is not valid:", category=UserWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*Automatically retrieving remote references.*")
        
        dataset = Dataset(
            datapackage=DataPackage.from_dict(datapackage_data(DATAPACKAGE_URL)),
            deployments=DeploymentsTable.from_table(table_content(DEPLOYMENTS_URL)),
            media=MediaTable.from_table(table_content(MEDIA_URL)),
            observations=ObservationsTable.from_table(table_content(OBSERVATIONS_URL))
        )
        dataset.save(master_tmp)
        
    return master_tmp


@pytest.fixture
def isolated_dataset_dir(master_dataset_dir, tmp_path) -> Path:
    """Automatically provides a fresh, untampered copy of the dataset for each test."""
    shutil.copytree(master_dataset_dir, tmp_path, dirs_exist_ok=True)
    return tmp_path

def tamper_csv(file_path, target_column, new_value):
    """Safely modifies a specific column in the first data row of a CSV."""
    with open(file_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)
        
    if target_column in headers and rows:
        col_idx = headers.index(target_column)
        rows[0][col_idx] = new_value

    with open(file_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def tamper_json(file_path, target_key, new_value):
    """Safely modifies a top-level key in a JSON dictionary."""
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
        
    data[target_key] = new_value
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

def _handle_report(report: Report):
    if report.valid:
        return True
    errors = report.errors
    for task in report.tasks:
        errors.extend(task.errors)
    raise ExceptionGroup(
        message=f'Found {len(errors)} errors during `frictionless` validation of: {report.description_text}',
        exceptions=[FrictionlessException(err) for err in errors]
    )

def test_validation_roundtrip(isolated_dataset_dir):
    """Tests that a pristine dataset successfully completes a load/save/validate cycle."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*Automatically retrieving remote references.*")
        report = validate(isolated_dataset_dir / "datapackage.json")
        _handle_report(report)

    loaded_dataset = Dataset.load(isolated_dataset_dir)
    
    resaved_dir = isolated_dataset_dir / "resaved"
    loaded_dataset.save(resaved_dir)
    
    resaved_dataset = Dataset.load(resaved_dir)
    assert loaded_dataset == resaved_dataset


@pytest.mark.parametrize(
    "filename, target_field, bad_value",
    [
        ("datapackage.json", "created", "Not_a_date"),
        ("deployments.csv", "latitude", "not_a_float"),
        ("media.csv", "timestamp", "14:30_on_a_tuesday"),
        ("observations.csv", "observationLevel", "invalid_enum_value"),
    ]
)
def test_schema_violations_raise_error(isolated_dataset_dir, filename, target_field, bad_value):
    """Tests that corrupting individual data fields triggers Pydantic ValidationErrors."""
    target_file = isolated_dataset_dir / filename
    
    # Apply structural tampering
    if target_file.suffix == ".csv":
        tamper_csv(target_file, target_field, bad_value)
    else:
        tamper_json(target_file, target_field, bad_value)
        
    # Attempting to load the corrupted directory should crash loudly
    with pytest.raises(ValidationError) as exc_info:
        Dataset.load(isolated_dataset_dir)
        
    # Verify the error message successfully identifies the broken column/key
    assert target_field in str(exc_info.value)