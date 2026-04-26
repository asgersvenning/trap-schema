[![PyPI version](https://img.shields.io/pypi/v/trap-schema.svg)](https://pypi.org/project/trap-schema/)
[![Python Versions](https://img.shields.io/pypi/pyversions/trap-schema.svg)](https://pypi.org/project/trap-schema/)
[![CI Status](https://github.com/asgersvenning/trap-schema/actions/workflows/ci.yaml/badge.svg)](https://github.com/asgersvenning/trap-schema/actions)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# trap-schema

An unofficial, strictly-typed implementation of the [Camtrap DP 1.0.2](https://camtrap-dp.tdwg.org/) datapackage standard. 

`trap-schema` uses Python dataclasses and Pydantic to provide robust, schema-aware data structures. It is designed to help developers easily parse, validate, and export camera trap data into the official Frictionless Data format without second-guessing schema constraints or having the documentation open on a second monitor.

## Features

* **Strict Validation:** Built on `pydantic` to enforce constraints (e.g., coordinate bounds, unique IDs, valid media types) at instantiation.
* **Ergonomic Tables:** Treat tabular data natively. Tables act as columnar data structures but guarantee per-row validation.
* **Auto-Synced Documentation:** Docstrings and schema attributes are automatically kept in sync with the official Camtrap DP JSON Schemas using a custom AST transformer.

## Installation

This project uses [`uv`](https://github.com/astral-sh/uv) for fast and reliable package management.

To add `trap-schema` to your project:

```bash
uv add trap-schema
```

## Quick Start

`trap-schema` is made primarily to facilate immediate errors via static analysis in your IDE or exceptions, so the following example does not show how you actually transform your data, merely how the interface for the containers in `trap-schema` are supposed to be used.

```py
# All Camtrap DP 1.0.2 Resources
from trap_schema import (
    Contributor,
    DataPackage,
    Dataset,
    DeploymentsRow,
    DeploymentsTable,
    License,
    MediaRow,
    MediaTable,
    ObservationsRow,
    ObservationsTable,
    Project,
    RelatedIdentifiers,
    Resource,
    Source,
    Taxonomic,
    Temporal,
)

# 1. Create validated rows
deployments_row = DeploymentsRow(
    deploymentID="dep_001",
    latitude=56.2,
    longitude=10.4,
    deploymentStart="2026-04-25T10:00:00Z",
    deploymentEnd="2026-05-25T10:00:00Z",
)

# 2. Group into a Table (validates unique keys and types)
deployments = DeploymentsTable(rows=[deployment])

# 3. Export table 
# (all file-backed resources share a `.save()` and `.load()` function for reading and loading to/from file)
deployments.save("out_dir")

# 4. Do the same for the other tables
media_data = ...
observations_data = ...
# (all row types can be created from a dictionary)
media_rows = [MediaRow.from_dict(data) for data in media_data]
observation_rows = [ObservationsRow.from_dict(data) for data in observations_data]
# (all tables are created via a list of rows)
media = MediaTable(rows=media_rows)
observations = ObservationsTable(rows=observations_rows)

# 5. Create the datapackage object
# (the `resources` and `profile` fields cannot be changed since they are "hardcoded" via the standard)
# * technically the standard allows additional resources, but this is a TODO for trap-schema
datapackage = DataPackage(
    name="my_dataset",
    id="...",
    ...,
    contributors=[
        Contributor(
            ...
        ),
        Contributor(
            ...
        )
    ],
    ...
) # See the docstring and/or https://camtrap-dp.tdwg.org/metadata/ for further details

# 6. Create the dataset
dataset = Dataset(
    datapackage=datapackage,
    deployments=deployments,
    media=media,
    observations=observations
)

# 7. Export dataset
dataset.save("<output_dir>")

# 8. (optional) Load dataset
# You can also load an existing dataset via:
new_dataset = Dataset.load("<dataset_dir>")
# or individual ressources
new_observations = ObservationsTable.load("<dataset_dir>")
# or
new_observations = ObservationsTable.load("<dataset_dir>/observations.csv")
# etc.
```

Run validation with `frictionless` via:

```bash
uvx frictionless validate <output_dir>/datapackage.json
```

## Development

```bash
git clone https://github.com/asgersvenning/trap-schema.git
cd trap-schema
uv sync --all-groups
```

### Update docstrings

We use `libcst` and `frictionless` to seamlessly and automatically integrate the official docstrings for table and metadata fields.

To update these run:

```py
uv run tools/docstrings.py
```

### Linting

```bash
[uv] ruff check --ignore E501
```

### Testing

```bash
uv run pytest tests
```

## License

[MIT](LICENSE)