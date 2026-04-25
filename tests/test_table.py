import urllib
import warnings

from trap_schema.tables import AbstractTable, DeploymentTable, MediaTable, ObservationsTable

from .helpers import DEPLOYMENTS_URL, MEDIA_URL, OBSERVATIONS_URL


def _test_table(url : str, table_cls : type[AbstractTable]):
    with urllib.request.urlopen(url) as resp:
        content = resp.read().decode()

    with warnings.catch_warnings():
        warnings.filterwarnings(
            action="ignore", 
            message="Provided JSON string is not valid:", 
            category=UserWarning
        )
        orig = table_cls.from_table(content)
        new = table_cls.from_table(orig.to_csv())

    assert len(orig) == len(new), f'{len(orig)=} != {len(new)=} '

def test_deployments():
    _test_table(DEPLOYMENTS_URL, DeploymentTable)

def test_media():
    _test_table(MEDIA_URL, MediaTable)

def test_observations():
    _test_table(OBSERVATIONS_URL, ObservationsTable)