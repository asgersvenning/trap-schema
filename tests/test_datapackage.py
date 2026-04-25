import json
import urllib.request

from trap_schema.datapackage import DataPackage

from .helpers import DATAPACKAGE_URL


def test_datapackage():
    with urllib.request.urlopen(DATAPACKAGE_URL) as resp:
        data = json.loads(resp.read())

    pkg = DataPackage.from_dict(data)
    assert isinstance(pkg, DataPackage)