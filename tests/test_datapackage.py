from trap_schema.datapackage import DataPackage

from .helpers import DATAPACKAGE_URL, datapackage_data


def test_datapackage(tmp_path):
    data = datapackage_data(DATAPACKAGE_URL)

    pkg = DataPackage.from_dict(data)
    assert isinstance(pkg, DataPackage)
    new_pkg = DataPackage.load(pkg.save(tmp_path))
    field_errs = []
    for field, info in DataPackage.model_fields.items():
        if (old := getattr(pkg, field)) != (new := getattr(new_pkg, field)):
            field_errs.append(f'{field}[{info}]: {old} != {new}')
    assert not field_errs, "\n".join(field_errs)

    