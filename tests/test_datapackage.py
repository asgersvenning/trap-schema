import json
import urllib.request

from trap_schema.datapackage import DataPackage

from .helpers import DATAPACKAGE_URL


def test_datapackage(tmp_path):
    with urllib.request.urlopen(DATAPACKAGE_URL) as resp:
        data = json.loads(resp.read())

    pkg = DataPackage.from_dict(data)
    assert isinstance(pkg, DataPackage)
    pkg.save(tmp_path)
    new_pkg = DataPackage.from_json(tmp_path / "datapackage.json")
    field_errs = []
    for field, info in DataPackage.model_fields.items():
        if (old := getattr(pkg, field)) != (new := getattr(new_pkg, field)):
            field_errs.append(f'{field}[{info}]: {old} != {new}')
    assert not field_errs, "\n".join(field_errs)

    