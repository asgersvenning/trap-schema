import json
import os
from pathlib import Path
from typing import Any

from trap_schema.base import AbstractContent


class SerializableModel(AbstractContent):
    """Base model providing ergonomic aliases and standard defaults for data export."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        return cls.model_validate(data)

    def to_dict(self, exclude_none: bool = True, by_alias: bool = True, **kwargs):
        return self.model_dump(exclude_none=exclude_none, by_alias=by_alias, mode="json", **kwargs)
    
    @classmethod
    def from_json(cls, js : Path | str | bytearray | bytes | dict):
        if isinstance(js, (str, Path)) and os.path.exists(js):
            with open(js) as f:
                data = json.load(f)
        elif hasattr(js, "read"):
            data = json.load(js)
        elif isinstance(js, (str, bytearray, bytes)):
            data = json.loads(js)
        elif isinstance(js, dict):
            data = js
        else:
            raise TypeError(
                f'Unknown type {type(js).__name__}, DataPackage.from_json only supports: `Path | str | bytearray | bytes | dict`'
            )
        return cls.from_dict(data)
    
    def to_json(self, path : str | Path):
        if isinstance(path, str):
            path = Path(path)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=True)
        return path
    
    @classmethod
    def file_name(cls):
        return cls.__name__.lower() + ".json"
    
    @classmethod
    def load(cls, path : str | Path, **kwargs):
        return cls.from_json(cls.file_path(path), **kwargs)

    def save(self, dir: str | Path = ".", **kwargs):
        return self.to_json(self.file_path(dir), **kwargs)