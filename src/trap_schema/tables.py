
from dataclasses import dataclass, field, fields

import os
import csv
import io
import types
from typing import Literal, Any, TypeVar, cast, get_type_hints, get_origin, get_args
from collections.abc import Callable, Sequence
import pandas as pd
import numpy as np

from trap_schema.fields import IsoTimestamp, TableJSON

import re

from pydantic import BaseModel

@dataclass(kw_only=True)
class AbstractTableRow(BaseModel):
    def constrain_numeric_attr(self, attr : str, min : float | int | None, max : float | int | None, required : bool):
        value : Any | float | int | None = getattr(self, attr)
        if not required and value is None:
            return True
        if value is None:
            raise ValueError(f'Required field `{attr}={value}`.')
        if not isinstance(value, (float, int)):
            raise TypeError(f'Cannot constrain `{min} <= {type(value)} <= {max}, for field `{attr}`.')
        not_in_range = False
        if min is not None and min > value:
            not_in_range = True
        if max is not None and max < value:
            not_in_range = True
        if not_in_range:
            raise ValueError(f'Field should be (inclusive) between {min} and {max}, but found `{attr}={value}`.')
        return True
    
    def match_str_attr(self, attr : str, pattern : str | re.Pattern, required : bool):
        value : Any | None = getattr(self, attr)
        if not required and value is None:
            return True
        if value is None:
            raise ValueError(f'Required field `{attr}={value}`.')
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        if not isinstance(value, str):
            raise TypeError(f'Cannot constrain `{type(value)}: {value}` to match pattern: {pattern}, for field `{attr}`.')
        if value is not None and not re.match(pattern, value):
            raise ValueError(
                f'Supplied `{attr}="{value}"` does not match required pattern `{pattern}`.'
            )
        return True

    def check_attributes(self, func : Callable[[Any], bool], attrs : Sequence[str]):
        return [attr for attr in attrs if not func(getattr(self, attr))]

    @classmethod
    def fields(cls):
        return list(cls.__dataclass_fields__.keys())
    
    @property
    def data(self):
        return {k : getattr(self, k) for k in self.fields()}
    
    def to_row(self, sep : str=","):
        row_values = []
        for k in self.fields():
            val = getattr(self, k)
            if val is None:
                row_values.append("")
                continue
            if isinstance(val, str):
                if sep in val or "\n" in val or '"' in val:
                    val = '"{}"'.format(val.replace('"', '""'))
                row_values.append(val)
            else:
                row_values.append(str(val))
        return sep.join(row_values)
    
    @classmethod
    def from_row(cls, row: str, sep: str = ",", headers: list[str] | None = None):
        """
        Parses a CSV string row into the dataclass.
        If headers are provided, it maps the CSV columns to the dataclass fields.
        Otherwise, it assumes the columns match the order of `cls.fields`.
        """
        reader = csv.reader(io.StringIO(row.strip()), delimiter=sep)
        try:
            parsed_values = next(reader)
        except StopIteration:
            raise ValueError(f'Provided row string ("{row}") is empty.')

        field_names = headers if headers else cls.fields()
        data = dict(zip(field_names, parsed_values))

        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: dict):
        hints = get_type_hints(cls)
        init_kwargs = {}

        for field_def in fields(cls):
            if not field_def.init or field_def.name not in data:
                continue

            raw_value = data[field_def.name]

            if raw_value == "" or raw_value is None:
                continue

            field_type = hints[field_def.name]
            origin = get_origin(field_type)
            args = get_args(field_type)

            if origin is types.UnionType:
                actual_types = [t for t in args if t is not type(None)]
                if actual_types:
                    field_type = actual_types[0]

            if isinstance(field_type, type) and isinstance(raw_value, field_type):
                init_kwargs[field_def.name] = raw_value
                continue

            try:
                if field_type is bool:
                    if isinstance(raw_value, str):
                        init_kwargs[field_def.name] = raw_value.lower() in ("true", "1", "yes", "y", "t")
                    else:
                        init_kwargs[field_def.name] = bool(raw_value)
                elif field_type in (int, float, str):
                    init_kwargs[field_def.name] = field_type(raw_value)
                elif isinstance(field_type, type) and field_type not in (list, dict, type(None)):
                    init_kwargs[field_def.name] = field_type(raw_value)
                else:
                    init_kwargs[field_def.name] = raw_value
            except (ValueError, TypeError) as e:
                raise ValueError(f"Failed to parse '{raw_value}' as {field_type} for field '{field_def.name}': {e}")

        return cls(**init_kwargs)
    
    def to_header(self, sep : str=","):
        return sep.join(self.fields())

K = TypeVar("K")

@dataclass(kw_only=True)
class AbstractTable[K: AbstractTableRow](BaseModel):
    rows: list[K] = field(default_factory=list)
    
    @property
    def unique_fields(self) -> tuple[str, ...]:
        raise NotImplementedError(f'`unique_fields` not implemented for {self}')

    @classmethod
    def get_row_cls(cls) -> type[K]:
        raise NotImplementedError(f'`get_row_cls` not implemented for {cls}')
    
    def __len__(self):
        return len(self.rows)

    def __post_init__(self):
        if len(self.rows) == 0:
            raise ValueError(
                'No row data supplied to table. At least one row must be supplied'
            )
        
        expected_cls = self.get_row_cls()
        invalid_row_types = set(type(row) for row in self.rows if not isinstance(row, expected_cls))
        
        if invalid_row_types:
            raise TypeError(
                'Unexpected table row types supplied:\n\t' +
                ', '.join(map(str, invalid_row_types))
            )
        
        self._data = {f: [getattr(row, f) for row in self.rows] for f in expected_cls.fields()}

        for attr in self.unique_fields:
            unique_vals = set(self._data[attr])
            if len(unique_vals) != len(self):
                raise ValueError(
                    f'Column "{attr}" must contain unique values, but found {len(unique_vals)}/{len(self)} unique values'
                )
            

    @property
    def data(self):
        return self._data
    
    def to_csv(self, path: str | None=None, sep: str = ",", linebreak: str = "\n"):
        lines = [self.rows[0].to_header(sep=sep)] + [row.to_row(sep=sep) for row in self.rows]
        file = linebreak.join(lines)
        if path is None:
            return file
        with open(path, "w") as f:
            f.write(file)
        return path
    
    @classmethod
    def _rows_from_text(cls, text: str, sep: str = ",", linebreak: str = "\n"):
        if "\n" not in text:
            with open(text, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = text

        lines = content.split(linebreak)
        if not lines or not lines[0].strip():
            raise ValueError("CSV is empty.")

        headers = next(csv.reader(io.StringIO(lines[0]), delimiter=sep))
        row_cls = cls.get_row_cls()
        
        if tuple(headers) != tuple(row_cls.fields()):
            print(f"WARNING: Columns in source CSV:\n\t{headers}\ndo not match expected rows:\n\t{row_cls.fields()}")
        
        return [row_cls.from_row(line, sep=sep, headers=headers) for line in map(str.strip, lines[1:]) if line]
    
    @classmethod
    def _rows_from_pandas(cls, df: pd.DataFrame):
        row_cls = cls.get_row_cls()
            
        return list(map(row_cls.from_dict, df.replace({np.nan: None, pd.NA: None}).to_dict(orient="records")))
    
    @classmethod
    def from_table(cls, table: str | pd.DataFrame, sep: str = ",", linebreak: str = "\n"):
        """
        Reads tabular data and instantiates the Table and all underlying rows.
        """
        if isinstance(table, str):
            rows = cls._rows_from_text(table, sep=sep, linebreak=linebreak)
        elif isinstance(table, pd.DataFrame):
            rows = cls._rows_from_pandas(table)
        else:
            raise NotImplementedError(f'`from_table` not implemented for {(type(table))}.')
                
        return cls(rows=rows)

@dataclass(kw_only=True)
class DeploymentRow(AbstractTableRow):
    deploymentID: str
    locationID: str | None = None
    locationName: str | None = None
    latitude: float
    longitude: float
    coordinateUncertainty: int | None = None
    deploymentStart: IsoTimestamp
    deploymentEnd: IsoTimestamp
    setupBy: str | None = None
    cameraID: str | None = None
    cameraModel: str | None = None
    cameraDelay: int | None = None
    cameraHeight: float | None = None
    cameraDepth: float | None = None
    cameraTilt: int | None = None
    cameraHeading: int | None = None
    detectionDistance: float | None = None
    timestampIssues: bool | None = None
    baitUse: bool | None = None
    featureType: Literal["roadPaved", "roadDirt", "trailHiking", "trailGame", "roadUnderpass", "roadOverpass", "roadBridge", "culvert", "burrow", "nestSite", "carcass", "waterSource", "fruitingTree"] | None = None
    habitat: str | None = None
    deploymentGroups: str | None = None
    deploymentTags: str | None = None
    deploymentComments: str | None = None

    def __post_init__(self):
        self.constrain_numeric_attr("latitude", -90, 90, True)
        self.constrain_numeric_attr("longitude", -180, 180, True)
        self.constrain_numeric_attr("coordinateUncertainty", 1, None, False)
        for attr in ["cameraDelay", "cameraHeight", "cameraDepth", "detectionDistance"]:
            self.constrain_numeric_attr(attr, 0, None, False)
        self.constrain_numeric_attr("cameraTilt", -90, 90, False)
        self.constrain_numeric_attr("cameraHeading", 0, 360, False)
    
@dataclass(kw_only=True)
class MediaRow(AbstractTableRow):
    mediaID: str
    deploymentID: str
    captureMethod: Literal["activityDetection", "timeLapse"] | None = None
    timestamp: IsoTimestamp
    filePath: str
    filePublic: bool
    fileName: str | None = None
    fileMediatype: str
    exifData: TableJSON | None = None
    favorite: bool | None = None
    mediaComments: str | None = None

    def __post_init__(self):
        self.match_str_attr("filePath", r'^(?=^[^./~])(^((?!\.{2}).)*$).*$', True)
        self.match_str_attr("fileMediatype", r'^(image|video|audio)/.*$', True)


@dataclass(kw_only=True)
class ObservationsRow(AbstractTableRow):
    observationID: str
    deploymentID: str
    mediaID: str | None = None
    eventID: str | None = None
    eventStart: IsoTimestamp
    eventEnd: IsoTimestamp
    observationLevel: Literal["media", "event"]
    observationType: Literal["animal", "human", "vehicle", "blank", "unknown", "unclassified"]
    cameraSetupType: Literal["setup", "calibration"] | None = None
    scientificName: str | None = None
    count: int | None = None
    lifeStage: Literal["adult", "subadult", "juvenile"] | None = None
    sex: Literal["female", "male"] | None = None
    behavior: str | None = None
    individualID: str | None = None
    individualPositionRadius: float | None = None
    individualPositionAngle: float | None = None
    individualSpeed: float | None = None
    bboxX: float | None = None
    bboxY: float | None = None
    bboxWidth: float | None = None
    bboxHeight: float | None = None
    classificationMethod: Literal["human", "machine"] | None = None
    classifiedBy: str | None = None
    classificationTimestamp: IsoTimestamp | None = None
    classificationProbability: float | None = None
    observationTags: str | None = None
    observationComments: str | None = None

    def __post_init__(self):
        self.constrain_numeric_attr("count", 1, None, False)
        self.constrain_numeric_attr("individualPositionRadius", 0, None, False)
        self.constrain_numeric_attr("individualPositionAngle", -90, 90, False)
        self.constrain_numeric_attr("individualSpeed", 0, None, False)
        for attr in ("bboxX", "bboxY", "classificationProbability"):
            self.constrain_numeric_attr(attr, 0, 1, False)
        for attr in ("bboxWidth", "bboxHeight"):
            self.constrain_numeric_attr(attr, 1e-15, 1, False)

@dataclass(kw_only=True)
class DeploymentTable(AbstractTable[DeploymentRow]):
    @property
    def unique_fields(self):
        return ("deploymentID", )
    @classmethod
    def get_row_cls(self):
        return DeploymentRow
    
    def save(self, dir : str=".", **kwargs):
        path = os.path.join(dir, "deployments.csv")
        return self.to_csv(path, **kwargs)

@dataclass(kw_only=True)
class MediaTable(AbstractTable[MediaRow]):
    @property
    def unique_fields(self):
        return ("mediaID", )
    @classmethod
    def get_row_cls(self):
        return MediaRow
    
    def save(self, dir : str=".", **kwargs):
        path = os.path.join(dir, "media.csv")
        return self.to_csv(path, **kwargs)

@dataclass(kw_only=True)
class ObservationsTable(AbstractTable[ObservationsRow]):
    @property
    def unique_fields(self):
        return ("observationID", )
    
    @classmethod
    def get_row_cls(self):
        return ObservationsRow
    
    def save(self, dir : str=".", **kwargs):
        path = os.path.join(dir, "observations.csv")
        return self.to_csv(path, **kwargs)

TABLE_TYPES : dict[str, type[AbstractTable]] = {
    "deployments.csv" : DeploymentTable,
    "media.csv" : MediaTable,
    "observations.csv" : ObservationsTable
}

def to_table(type : str, **kwargs):
    cls : type[AbstractTable] = TABLE_TYPES[type]
    return cls(**kwargs)