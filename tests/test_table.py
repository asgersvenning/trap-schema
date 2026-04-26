import warnings
from pathlib import Path

from trap_schema.tables import AbstractTable, DeploymentsTable, MediaTable, ObservationsTable

from .helpers import DEPLOYMENTS_URL, MEDIA_URL, OBSERVATIONS_URL, table_content


def _test_table(tmp_path : Path, url : str, table_cls : type[AbstractTable]):
    content = table_content(url)

    with warnings.catch_warnings():
        warnings.filterwarnings(
            action="ignore", 
            message="Provided JSON string is not valid:", 
            category=UserWarning
        )
        orig = table_cls.from_table(content)
        new = table_cls.load(orig.save(tmp_path))

    assert len(orig) == len(new), f'{len(orig)=} != {len(new)=} '

def test_deployments(tmp_path):
    _test_table(tmp_path, DEPLOYMENTS_URL, DeploymentsTable)

def test_media(tmp_path):
    _test_table(tmp_path, MEDIA_URL, MediaTable)

def test_observations(tmp_path):
    _test_table(tmp_path, OBSERVATIONS_URL, ObservationsTable)