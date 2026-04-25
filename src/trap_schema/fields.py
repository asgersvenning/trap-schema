import json
import warnings
from datetime import UTC, date, datetime
from functools import total_ordering
from typing import Any

from geojson import GeoJSON
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


@total_ordering
class IsoDate:
    """
    A flexible date parser that accepts strings, integers, datetimes, or dates,
    and aggressively normalizes them to a strict YYYY-MM-DD format.
    """
    def __init__(self, value: str | int | datetime | date):
        if isinstance(value, str) and value.isdigit():
            value = int(value)
            
        if isinstance(value, int):
            self._date = datetime.fromtimestamp(value, UTC).date()
        elif isinstance(value, str):
            # Attempt to grab just the YYYY-MM-DD portion first. 
            # This safely ignores any trailing time/timezone information like 'T10:00:00Z'
            try:
                self._date = date.fromisoformat(value[:10])
            except ValueError:
                # Fallback for irregular but valid ISO formats
                self._date = datetime.fromisoformat(value).date()
        elif isinstance(value, datetime):
            self._date = value.date()
        elif isinstance(value, date):
            self._date = value
        else:
            raise NotImplementedError(
                f'`IsoDate` only supports strings, integers, datetime and date objects, not {type(value)}'
            )

    def __str__(self):
        return self._date.isoformat()
    
    def __repr__(self):
        return f'{type(self).__name__}[{str(self)}]'
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, IsoDate):
            return self._date == other._date
        if isinstance(other, (date, datetime)):
            compare_target = other.date() if isinstance(other, datetime) else other
            return self._date == compare_target
        if isinstance(other, str):
            try:
                return self._date == IsoDate(other)._date
            except (ValueError, TypeError, NotImplementedError):
                return False
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, IsoDate):
            return self._date < other._date
        if isinstance(other, (date, datetime)):
            compare_target = other.date() if isinstance(other, datetime) else other
            return self._date < compare_target
        return NotImplemented

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
    def _validate(cls, value: Any) -> "IsoDate":
        if isinstance(value, cls):
            return value
        return cls(value)

@total_ordering
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
    
    def __repr__(self):
        return f'{type(self).__name__}[{str(self)}]'
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, IsoTimestamp):
            return self._timestamp == other._timestamp
        if isinstance(other, datetime):
            return self._timestamp == other
        if isinstance(other, str):
            try:
                return self._timestamp == IsoTimestamp(other)._timestamp
            except (ValueError, TypeError, NotImplementedError):
                return False
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, IsoTimestamp):
            return self._timestamp < other._timestamp
        if isinstance(other, datetime):
            return self._timestamp < other
        return NotImplemented

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
                warnings.warn('Provided JSON string is not valid:\n\t{}'.format("\n\t".join(value.splitlines())), category=UserWarning)
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