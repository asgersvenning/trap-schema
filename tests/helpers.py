import json
import urllib.request

DATAPACKAGE_URL = "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/example/datapackage.json"
DEPLOYMENTS_URL = "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/example/deployments.csv"
MEDIA_URL = "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/example/media.csv"
OBSERVATIONS_URL = "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/example/observations.csv"

def table_content(url : str):
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode()

def datapackage_data(url : str):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())