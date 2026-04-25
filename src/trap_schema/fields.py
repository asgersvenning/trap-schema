import json
from datetime import datetime, timezone
from geojson import GeoJSON

class IsoTimestamp:
    def __init__(self, value : str | int | datetime):
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if isinstance(value, int):
            self._timestamp = datetime.fromtimestamp(value, timezone.utc)
        elif isinstance(value, str):
            self._timestamp = datetime.fromisoformat(value)
        elif isinstance(value, datetime):
            self._timestamp = value
        else:
            raise NotImplementedError(
                f'`IsoTimestamp` only supports strings, integers and existing `datetime.datetime` objects, not {type(value)}'
            )
        assert self._timestamp.tzinfo is not None, f'IsoTimestamp must be associated with a timezone, but was initialized from {value} of type {type(value)}'

    def __str__(self):
        return self._timestamp.isoformat()


class TableJSON(dict):
    def __init__(self, value: dict | str, strict: bool = False):
        self._str_orig = None
        self._is_valid = True
        
        if isinstance(value, str):
            self._str_orig = value
            cleaned_value = value.strip()
            
            if cleaned_value.startswith('"') and cleaned_value.endswith('"'):
                cleaned_value = cleaned_value[1:-1].replace('""', '"')
            
            try:
                super().__init__(json.loads(cleaned_value))
            except json.JSONDecodeError:
                if strict:
                    raise
                print('WARNING: Provided JSON string is not valid:\n\t{}'.format("\n\t".join(value.splitlines())))
                self._is_valid = False
                super().__init__()
        else:
            super().__init__(value)

    def __str__(self):
        if self._str_orig is not None:
            if self._str_orig.startswith('"'):
                return self._str_orig
            else:
                return '"{}"'.format(self._str_orig.replace('"', '""'))
        
        json_str = json.dumps(self, separators=(',', ':'))
        return '"' + json_str.replace('"', '""') + '"'


class GeoJSONWrapper(GeoJSON):
    def to_dict(self):
        return dict(self)