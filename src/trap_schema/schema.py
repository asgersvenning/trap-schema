import dataclasses
from dataclasses import dataclass
import types
from typing import Any, get_origin, get_args, get_type_hints
from pydantic import BaseModel

@dataclass(kw_only=True)
class SerializableModel(BaseModel):
    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        if data is None:
            raise TypeError('No data provided.')

        # 1. Grab the type annotations for the current class
        hints = get_type_hints(cls)
        init_kwargs = {}

        for field in dataclasses.fields(cls):
            # Skip fields not in data or fields locked down with init=False
            if not field.init or field.name not in data:
                continue

            value = data[field.name]
            if value is None:
                continue

            # 2. Introspect the field's type hint
            field_type = hints[field.name]
            origin = get_origin(field_type)
            args = get_args(field_type)

            # Handle `Type | None` (Union types)
            if origin is types.UnionType:
                # Isolate the actual type (e.g., stripping None)
                actual_types = [t for t in args if t is not type(None)]
                if actual_types:
                    field_type = actual_types[0]
                    origin = get_origin(field_type)
                    args = get_args(field_type)

            # 3. Recursive Instantiation: Lists of SerializableModels
            if origin is list and args:
                list_item_type = args[0]
                if isinstance(list_item_type, type) and issubclass(list_item_type, SerializableModel):
                    init_kwargs[field.name] = [list_item_type.from_dict(item) for item in value]
                else:
                    init_kwargs[field.name] = value # Native list (e.g., list[str])

            # 4. Recursive Instantiation: Nested SerializableModels
            elif isinstance(field_type, type) and issubclass(field_type, SerializableModel):
                init_kwargs[field.name] = field_type.from_dict(value)

            # 5. Instantiation for custom non-Serializable classes (IsoTimestamp, GeoJSON)
            elif isinstance(field_type, type) and field_type not in (str, int, float, bool, list, dict, type(None)):
                # This explicitly executes: IsoTimestamp(value) or GeoJSON(value)
                init_kwargs[field.name] = field_type(value)

            # 6. Native types or pass-through
            else:
                init_kwargs[field.name] = value

        return cls(**init_kwargs)

    def to_dict(self) -> dict[str, Any]:
        """
        Recursively converts the dataclass to a dictionary.
        Uses a smart factory to seamlessly handle the inverse of Step 5
        by downcasting custom objects back to primitives.
        """
        def smart_factory(data: list[tuple[str, Any]]) -> dict[str, Any]:
            result = {}
            for key, value in data:
                # Inverse of Step 5: Handle custom non-Serializable classes
                if value is None:
                    continue
                if not isinstance(value, (str, int, float, bool, list, dict)): 
                    if hasattr(value, "to_dict"):
                        result[key] = value.to_dict()
                    # Fallback for simple wrappers (like IsoTimestamp)
                    else:
                        result[key] = str(value)
                # Native primitives and already-parsed nested dicts
                else:
                    result[key] = value

            return result

        return dataclasses.asdict(self, dict_factory=smart_factory)