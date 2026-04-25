import json
from datetime import UTC, datetime
from typing import Any

from geojson import GeoJSON
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class IsoTimestamp:
    def __init__(self, value: str | int | datetime):
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if isinstance(value, int):
            self._timestamp = datetime.fromtimestamp(value, UTC)
        elif isinstance(value, str):
            self._timestamp = datetime.fromisoformat(value)
        elif isinstance(value, datetime):
            self._timestamp = value
        else:
            raise NotImplementedError(
                f'`IsoTimestamp` only supports strings, integers and existing `datetime.datetime` objects, not {type(value)}'
            )
        if self._timestamp.tzinfo is None:
            raise ValueError(
                f'IsoTimestamp must be associated with a timezone, but was initialized from {value} of type {type(value)}'
            )

    def __str__(self):
        return self._timestamp.isoformat()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: str(instance),
                when_used='json'
            )
        )

    @classmethod
    def _validate(cls, value: Any) -> "IsoTimestamp":
        if isinstance(value, cls):
            return value
        return cls(value)


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

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: dict(instance), # Serialize back to a standard dict for JSON output
                when_used='json'
            )
        )

    @classmethod
    def _validate(cls, value: Any) -> "TableJSON":
        if isinstance(value, cls):
            return value
        return cls(value)


class GeoJSONWrapper(GeoJSON):
    def to_dict(self):
        return dict(self)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: instance.to_dict(),
                when_used='json'
            )
        )

    @classmethod
    def _validate(cls, value: Any) -> "GeoJSONWrapper":
        if isinstance(value, cls):
            return value
        # Handle dict unpacking if initialized from a raw dictionary mapping
        if isinstance(value, dict):
            return cls(**value)
        return cls(value)