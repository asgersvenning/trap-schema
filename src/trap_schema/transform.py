from dataclasses import dataclass, field
from typing import TypeVar, Any
from collections.abc import Callable, Sequence
import re
from datetime import datetime, timezone
import pandas as pd

@dataclass
class ColumnMap:
    """Represents a single mapping from a source column to a destination table/column."""
    src_column: str | None
    dst_column: str
    transform: Callable[[Any, dict], Any] = field(default=lambda x, y : x)

    def __call__(self, src: dict | pd.Series, dst: dict):
        val = src[self.src_column] if self.src_column is not None else None
        dst[self.dst_column] = self.transform(val, src)


class Transformer:
    def __init__(self, mappers : Sequence[ColumnMap]):
        self.mappers = mappers

    def __call__(self, src : dict | pd.Series | pd.DataFrame):
        if not isinstance(src, (dict, pd.Series, pd.DataFrame)):
            raise TypeError(f'Expected `dict` or `pd.Series` but got {type(src)}')
        if isinstance(src, pd.DataFrame):
            if not len(src):
                raise ValueError(
                    f'Cannot transform `src` pd.DataFrame with {len(src)} rows, src must only contain 1 row, if it is a dataframe.'
                )
            src = src.iloc[0]
        if isinstance(src, pd.Series):
            src = src.to_dict()
        dst = dict()
        for mapper in self.mappers:
            mapper(src, dst)
        return dst

    def __len__(self):
        return len(self.mappers)
    
    def __getitem__(self, i):
        return self.mappers[i]
    
    def __iter__(self):
        yield from self.mappers


def calc_width(max_width : int, coordinate_names : tuple=("x1", "x2")):
    def inner(val, row : dict) -> float:
        return (
            float(row[coordinate_names[1]]) - float(row[coordinate_names[0]])
        ) / max_width if all(cn in row for cn in coordinate_names) else None
    return inner

def calc_height(max_width : int, coordinate_names : tuple=("y1", "y2")):
    def inner(val, row : dict) -> float:
        return (
            float(row[coordinate_names[1]]) - float(row[coordinate_names[0]])
        ) / max_width if all(cn in row for cn in coordinate_names) else None
    return inner

def parse_wkt_point_longitude(val, row) -> str | None:
    if val:
        match = re.search(r"POINT\(([-\d\.]+)\s([-\d\.]+)\)", str(val))
        return match.group(1) if match else None
    return None

def parse_wkt_point_latitude(val, row) -> str | None:
    if val:
        match = re.search(r"POINT\(([-\d\.]+)\s([-\d\.]+)\)", str(val))
        return match.group(2) if match else None
    return None

def _timestamp_to_iso(x : int | str, timespec="auto"):
    return datetime.fromtimestamp(int(x), timezone.utc).isoformat(timespec=timespec)

def timestamp_to_iso(val, row) -> str | None:
    if val:
        return _timestamp_to_iso(val)
    return None

V = TypeVar("V")

def hardcode(value : V):
    def inner(val, row) -> V:
        # Ignores the source data and forces a hardcoded value
        return value
    return inner