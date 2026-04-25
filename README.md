# trap-schema

An unofficial, strictly-typed implementation of the [Camtrap DP 1.0.2](https://camtrap-dp.tdwg.org/) datapackage standard. 

`trap-schema` uses Python dataclasses and Pydantic to provide robust, schema-aware data structures. It is designed to help developers easily parse, validate, and export camera trap data into the official Frictionless Data format without second-guessing schema constraints
or having the documentation open on a second monitor.

## Features

* **Strict Validation:** Built on `pydantic` to enforce constraints (e.g., coordinate bounds, unique IDs, valid media types) at instantiation.
* **Ergonomic Tables:** Treat tabular data natively. Tables act as columnar data structures but guarantee per-row validation.
* **Auto-Synced Documentation:** Docstrings and schema attributes are automatically kept in sync with the official Camtrap DP JSON Schemas using a custom AST transformer.

## Installation

This project uses [`uv`](https://github.com/astral-sh/uv) for fast and reliable package management. Requires Python 3.14+.

To add `trap-schema` to your project:

```bash
uv add git+https://github.com/asgersvenning/trap-schema.git
```

To install a specific release (e.g. `v0.1.0`):

```bash
uv add git+https://github.com/asgersvenning/trap-schema.git@v0.1.0
```

## Quick Start

```py
from trap_schema.tables import DeploymentRow, DeploymentTable

# 1. Create validated rows
deployment = DeploymentRow(
    deploymentID="dep_001",
    latitude=56.2,
    longitude=10.4,
    deploymentStart="2026-04-25T10:00:00Z",
    deploymentEnd="2026-05-25T10:00:00Z",
)

# 2. Group into a Table (validates unique keys and types)
table = DeploymentTable(rows=[deployment])

# 3. Export to Camtrap DP standard CSV
table.save("out_dir")
```

## Development

```bash
git clone [https://github.com/asgersvenning/trap-schema.git](https://github.com/asgersvenning/trap-schema.git)
cd trap-schema
uv sync --all-groups
```

### Update docstrings

We use `libcst` and `frictionless` to seamlessly and automatically integrate the official docstrings for table and metadata fields.

To update these run:

```py
uv run tools/docstrings.py
```

### Linting & Testing

Coming soon. *(Contributions appreciated!)*

## License

[MIT](LICENSE)