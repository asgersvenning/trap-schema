from typing import Any

from pydantic import BaseModel


class SerializableModel(BaseModel):
    """Base model providing ergonomic aliases and standard defaults for data export."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        return cls.model_validate(data)

    def to_dict(self, exclude_none: bool = True, by_alias: bool = True, **kwargs):
        return self.model_dump(exclude_none=exclude_none, by_alias=by_alias, **kwargs)