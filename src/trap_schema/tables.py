import csv
import io
import os
from collections.abc import Sequence
from typing import Annotated, Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, PrivateAttr

from trap_schema.fields import IsoTimestamp, TableJSON


class AbstractTableRow(BaseModel):
    @classmethod
    def fields(cls):
        return list(cls.model_fields.keys())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]):
        return cls.model_validate(data)
    
    def to_dict(self):
        return self.model_dump()

    @property
    def data(self):
        return self.to_dict()

    def to_row(self, sep: str = ","):
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
        Parses a CSV string row. Converts empty CSV strings to None 
        so Pydantic handles optionals perfectly.
        """
        reader = csv.reader(io.StringIO(row.strip()), delimiter=sep)
        try:
            parsed_values = next(reader)
        except StopIteration:
            raise ValueError(f'Provided row string ("{row}") is empty.')

        field_names = headers if headers else cls.fields()
        
        data = {
            k: (v if v != "" else None) 
            for k, v in zip(field_names, parsed_values)
        }

        return cls.from_dict(data)

    def to_header(self, sep: str = ","):
        return sep.join(self.fields())

class AbstractTable[K: AbstractTableRow](BaseModel):
    rows: list[K] = Field(default_factory=list)
    _data: dict = PrivateAttr(default_factory=dict)

    def __getattr__(self, attr : str):
        if attr.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{attr}'")

        try:
            return self.data[attr]
        except KeyError:
            raise AttributeError(f"Table has no column '{attr}'")

    @property
    def unique_fields(self) -> tuple[str, ...]:
        raise NotImplementedError(f"`unique_fields` not implemented for {self}")

    @classmethod
    def get_row_cls(cls) -> type[K]:
        raise NotImplementedError(f"`get_row_cls` not implemented for {cls}")

    def __len__(self):
        return len(self.rows)

    def model_post_init(self, __context: Any) -> None:
        if len(self.rows) == 0:
            raise ValueError("No row data supplied to table. At least one row must be supplied")

        expected_cls = self.get_row_cls()
        invalid_row_types = set(type(row) for row in self.rows if not isinstance(row, expected_cls))

        if invalid_row_types:
            raise TypeError("Unexpected table row types supplied:\n\t" + ", ".join(map(str, invalid_row_types)))

        self._data = {f: [getattr(row, f) for row in self.rows] for f in expected_cls.fields()}

        for attr in self.unique_fields:
            unique_vals = set(self._data[attr])
            if len(unique_vals) != len(self):
                raise ValueError(
                    f'Column "{attr}" must contain unique values, but found {len(unique_vals)}/{len(self)} unique values'
                )
            
    @classmethod
    def from_dict(cls, data: dict[str, Sequence[Any]]) -> "AbstractTable":
        """Instantiates the table from a columnar dictionary."""
        if not data:
            return cls(rows=[])
            
        row_cls = cls.get_row_cls()
        lengths = [len(col) for col in data.values()]
        
        if len(set(lengths)) > 1:
            raise ValueError(f"Heterogeneous column lengths: {dict(zip(data.keys(), lengths))}")
            
        nrow = lengths[0] if lengths else 0
        keys = list(data.keys())
        
        rows = [
            row_cls.from_dict({k: data[k][i] for k in keys}) 
            for i in range(nrow)
        ]
        
        return cls(rows=rows)

    def to_dict(self):
        return self._data

    @property
    def data(self):
        return self.to_dict()

    def to_csv(self, path: str | None = None, sep: str = ",", linebreak: str = "\n"):
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
            with open(text, encoding="utf-8") as f:
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
            raise NotImplementedError(f"`from_table` not implemented for {(type(table))}.")

        return cls(rows=rows)

class DeploymentRow(AbstractTableRow):
    """Table with camera trap placements (deployments). Includes `deploymentID`, start, end, location and
    camera setup information.

    Arguments:
        deploymentID: Unique identifier of the deployment.
        locationID: Identifier of the deployment location.
        locationName: Name given to the deployment location.
        latitude: Latitude of the deployment location in decimal degrees, using the WGS84 datum.
        longitude: Longitude of the deployment location in decimal degrees, using the WGS84 datum.
        coordinateUncertainty: Horizontal distance from the given `latitude` and `longitude` describing the smallest circle
            containing the deployment location. Expressed in meters. Especially relevant when
            coordinates are rounded to protect sensitive species.
        deploymentStart: Date and time at which the deployment was started. Formatted as an ISO 8601 string with timezone
            designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        deploymentEnd: Date and time at which the deployment was ended. Formatted as an ISO 8601 string with timezone
            designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        setupBy: Name or identifier of the person or organization that deployed the camera.
        cameraID: Identifier of the camera used for the deployment (e.g. the camera device serial number).
        cameraModel: Manufacturer and model of the camera. Formatted as `manufacturer-model`.
        cameraDelay: Predefined duration after detection when further activity is ignored. Expressed in seconds.
        cameraHeight: Height at which the camera was deployed. Expressed in meters. Not to be combined with `cameraDepth`.
        cameraDepth: Depth at which the camera was deployed. Expressed in meters. Not to be combined with `cameraHeight`.
        cameraTilt: Angle at which the camera was deployed in the vertical plane. Expressed in degrees, with `-90`
            facing down, `0` horizontal and `90` facing up.
        cameraHeading: Angle at which the camera was deployed in the horizontal plane. Expressed in decimal degrees
            clockwise from north, with values ranging from `0` to `360`: `0` = north, `90` = east,
            `180` = south, `270` = west.
        detectionDistance: Maximum distance at which the camera can reliably detect activity. Expressed in meters. Typically
            measured by having a human move in front of the camera.
        timestampIssues: `true` if timestamps in the `media` resource for the deployment are known to have (unsolvable)
            issues (e.g. unknown timezone, am/pm switch).
        baitUse: `true` if bait was used for the deployment. More information can be provided in `tags` or
            `comments`.
        featureType: Type of the feature (if any) associated with the deployment.
        habitat: Short characterization of the habitat at the deployment location.
        deploymentGroups: Deployment group(s) associated with the deployment. Deployment groups can have a spatial (arrays,
            grids, clusters), temporal (sessions, seasons, months, years) or other context.
            Formatted as a pipe (`|`) separated list for multiple values, with values preferably
            formatted as `key:value` pairs.
        deploymentTags: Tag(s) associated with the deployment. Formatted as a pipe (`|`) separated list for multiple values,
            with values optionally formatted as `key:value` pairs.
        deploymentComments: Comments or notes about the deployment.

    """
    deploymentID: str
    """Unique identifier of the deployment."""
    locationID: str | None = None
    """Identifier of the deployment location."""
    locationName: str | None = None
    """Name given to the deployment location."""
    latitude: Annotated[float, Field(ge=-90, le=90)]
    """Latitude of the deployment location in decimal degrees, using the WGS84 datum."""
    longitude: Annotated[float, Field(ge=-180, le=180)]
    """Longitude of the deployment location in decimal degrees, using the WGS84 datum."""
    coordinateUncertainty: Annotated[int | None, Field(ge=1)] = None
    """Horizontal distance from the given `latitude` and `longitude` describing the smallest circle
    containing the deployment location. Expressed in meters. Especially relevant when coordinates
    are rounded to protect sensitive species."""
    deploymentStart: IsoTimestamp
    """Date and time at which the deployment was started. Formatted as an ISO 8601 string with timezone
    designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`)."""
    deploymentEnd: IsoTimestamp
    """Date and time at which the deployment was ended. Formatted as an ISO 8601 string with timezone
    designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`)."""
    setupBy: str | None = None
    """Name or identifier of the person or organization that deployed the camera."""
    cameraID: str | None = None
    """Identifier of the camera used for the deployment (e.g. the camera device serial number)."""
    cameraModel: str | None = None
    """Manufacturer and model of the camera. Formatted as `manufacturer-model`."""
    cameraDelay: Annotated[int | None, Field(ge=0)] = None
    """Predefined duration after detection when further activity is ignored. Expressed in seconds."""
    cameraHeight: Annotated[float | None, Field(ge=0)] = None
    """Height at which the camera was deployed. Expressed in meters. Not to be combined with `cameraDepth`."""
    cameraDepth: Annotated[float | None, Field(ge=0)] = None
    """Depth at which the camera was deployed. Expressed in meters. Not to be combined with `cameraHeight`."""
    cameraTilt: Annotated[int | None, Field(ge=-90, le=90)] = None
    """Angle at which the camera was deployed in the vertical plane. Expressed in degrees, with `-90`
    facing down, `0` horizontal and `90` facing up."""
    cameraHeading: Annotated[int | None, Field(ge=0, le=360)] = None
    """Angle at which the camera was deployed in the horizontal plane. Expressed in decimal degrees
    clockwise from north, with values ranging from `0` to `360`: `0` = north, `90` = east, `180` =
    south, `270` = west."""
    detectionDistance: Annotated[float | None, Field(ge=0)] = None
    """Maximum distance at which the camera can reliably detect activity. Expressed in meters. Typically
    measured by having a human move in front of the camera."""
    timestampIssues: bool | None = None
    """`true` if timestamps in the `media` resource for the deployment are known to have (unsolvable)
    issues (e.g. unknown timezone, am/pm switch)."""
    baitUse: bool | None = None
    """`true` if bait was used for the deployment. More information can be provided in `tags` or
    `comments`."""
    featureType: Literal["roadPaved", "roadDirt", "trailHiking", "trailGame", "roadUnderpass", "roadOverpass", "roadBridge", "culvert", "burrow", "nestSite", "carcass", "waterSource", "fruitingTree"] | None = None
    """Type of the feature (if any) associated with the deployment."""
    habitat: str | None = None
    """Short characterization of the habitat at the deployment location."""
    deploymentGroups: str | None = None
    """Deployment group(s) associated with the deployment. Deployment groups can have a spatial (arrays,
    grids, clusters), temporal (sessions, seasons, months, years) or other context. Formatted as a
    pipe (`|`) separated list for multiple values, with values preferably formatted as `key:value`
    pairs."""
    deploymentTags: str | None = None
    """Tag(s) associated with the deployment. Formatted as a pipe (`|`) separated list for multiple values,
    with values optionally formatted as `key:value` pairs."""
    deploymentComments: str | None = None
    """Comments or notes about the deployment."""

class MediaRow(AbstractTableRow):
    """Table with media files (images/videos) recorded during deployments (`deploymentID`). Includes
    timestamp and file path.

    Arguments:
        mediaID: Unique identifier of the media file.
        deploymentID: Identifier of the deployment the media file belongs to. Foreign key to `deployments.deploymentID`.
        captureMethod: Method used to capture the media file.
        timestamp: Date and time at which the media file was recorded. Formatted as an ISO 8601 string with timezone
            designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        filePath: URL or relative path to the media file, respectively for externally hosted files or files that are
            part of the package.
        filePublic: `false` if the media file is not publicly accessible (e.g. to protect the privacy of people).
        fileName: Name of the media file. If provided, one should be able to sort media files chronologically within a
            deployment on `timestamp` (first) and `fileName` (second).
        fileMediatype: Mediatype of the media file. Expressed as an [IANA Media
            Type](https://www.iana.org/assignments/media-types/media-types.xhtml).
        exifData: EXIF data of the media file. Formatted as a valid JSON object.
        favorite: `true` if the media file is deemed of interest (e.g. an exemplar image of an individual).
        mediaComments: Comments or notes about the media file.

    """
    mediaID: str
    """Unique identifier of the media file."""
    deploymentID: str
    """Identifier of the deployment the media file belongs to. Foreign key to `deployments.deploymentID`."""
    captureMethod: Literal["activityDetection", "timeLapse"] | None = None
    """Method used to capture the media file."""
    timestamp: IsoTimestamp
    """Date and time at which the media file was recorded. Formatted as an ISO 8601 string with timezone
    designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`)."""
    filePath: Annotated[str, Field(pattern=r"^[^./~][^.]*(\.[^.]+)*\.?$")]  # Note: this regex doesn't match the one given in the standard ("^(?=^[^./~])(^((?!\.{2}).)*$).*$") because pydantic doesn't support lookaround
    """URL or relative path to the media file, respectively for externally hosted files or files that are
    part of the package."""
    filePublic: bool
    """`false` if the media file is not publicly accessible (e.g. to protect the privacy of people)."""
    fileName: str | None = None
    """Name of the media file. If provided, one should be able to sort media files chronologically within a
    deployment on `timestamp` (first) and `fileName` (second)."""
    fileMediatype: Annotated[str, Field(pattern=r"^(image|video|audio)/.*$")]
    """Mediatype of the media file. Expressed as an [IANA Media
    Type](https://www.iana.org/assignments/media-types/media-types.xhtml)."""
    exifData: TableJSON | None = None
    """EXIF data of the media file. Formatted as a valid JSON object."""
    favorite: bool | None = None
    """`true` if the media file is deemed of interest (e.g. an exemplar image of an individual)."""
    mediaComments: str | None = None
    """Comments or notes about the media file."""

class ObservationsRow(AbstractTableRow):
    """Table with observations derived from the media files. Associated with deployments (`deploymentID`).
    Observations can mark non-animal events (camera setup, human, blank) or one or more animal
    observations (`observationType` = `animal`) of a certain taxon, count, life stage, sex, behavior
    and/or individual. Observations can be made at different levels (`observationLevel`).

    Arguments:
        observationID: Unique identifier of the observation.
        deploymentID: Identifier of the deployment the observation belongs to. Foreign key to `deployments.deploymentID`.
        mediaID: Identifier of the media file that was classified. Only applicable for media-based observations
            (`observationLevel` = `media`). Foreign key to `media.mediaID`.
        eventID: Identifier of the event the observation belongs to. Facilitates linking event-based and media-based
            observations with a permanent identifier.
        eventStart: Date and time at which the event started. Formatted as an ISO 8601 string with timezone designator
            (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        eventEnd: Date and time at which the event ended. Formatted as an ISO 8601 string with timezone designator
            (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        observationLevel: Level at which the observation was classified. `media` for media-based observations that are
            directly associated with a media file (`mediaID`). These are especially useful for
            machine learning and don't need to be mutually exclusive (e.g. multiple classifications
            are allowed). `event` for event-based observations that consider an event (comprising a
            collection of media files). These are especially useful for ecological research and
            should be mutually exclusive, so that their `count` can be summed.
        observationType: Type of the observation. All categories in this vocabulary have to be understandable from an AI
            point of view. `unknown` describes classifications with a `classificationProbability`
            below some predefined threshold i.e. neither humans nor AI can say what was recorded.
        cameraSetupType: Type of the camera setup action (if any) associated with the observation.
        scientificName: Scientific name of the observed individual(s).
        count: Number of observed individuals (optionally of given life stage, sex and behavior).
        lifeStage: Age class or life stage of the observed individual(s).
        sex: Sex of the observed individual(s)
        behavior: Dominant behavior of the observed individual(s), preferably expressed as controlled values (e.g.
            grazing, browsing, rooting, vigilance, running, walking). Formatted as a pipe (`|`)
            separated list for multiple values, with the dominant behavior listed first.
        individualID: Identifier of the observed individual.
        individualPositionRadius: Distance from the camera to the observed individual identified by `individualID`. Expressed in
            meters. Required for distance analyses (e.g. [Howe et al.
            2017](https://doi.org/10.1111/2041-210X.12790)) and random encounter modelling (e.g.
            [Rowcliffe et al. 2011](https://doi.org/10.1111/j.2041-210X.2011.00094.x)).
        individualPositionAngle: Angular distance from the camera view centerline to the observed individual identified by
            `individualID`. Expressed in degrees, with negative values left, `0` straight ahead and
            positive values right. Required for distance analyses (e.g. [Howe et al.
            2017](https://doi.org/10.1111/2041-210X.12790)) and random encounter modelling (e.g.
            [Rowcliffe et al. 2011](https://doi.org/10.1111/j.2041-210X.2011.00094.x)).
        individualSpeed: Average movement speed of the observed individual identified by `individualID`. Expressed in meters
            per second. Required for random encounter modelling (e.g. [Rowcliffe et al.
            2016](https://doi.org/10.1002/rse2.17)).
        bboxX: Horizontal position of the top-left corner of a bounding box that encompasses the observed
            individual(s) in the media file identified by `mediaID`. Or the horizontal position of
            an object in that media file. Measured from the left and relative to media file width.
        bboxY: Vertical position of the top-left corner of a bounding box that encompasses the observed
            individual(s) in the media file identified by `mediaID`. Or the vertical position of an
            object in that media file. Measured from the top and relative to the media file height.
        bboxWidth: Width of a bounding box that encompasses the observed individual(s) in the media file identified by
            `mediaID`. Measured from the left of the bounding box and relative to the media file
            width.
        bboxHeight: Height of the bounding box that encompasses the observed individual(s) in the media file identified
            by `mediaID`. Measured from the top of the bounding box and relative to the media file
            height.
        classificationMethod: Method (most recently) used to classify the observation.
        classifiedBy: Name or identifier of the person or AI algorithm that (most recently) classified the observation.
        classificationTimestamp: Date and time of the (most recent) classification. Formatted as an ISO 8601 string with timezone
            designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        classificationProbability: Degree of certainty of the (most recent) classification. Expressed as a probability, with `1` being
            maximum certainty. Omit or provide an approximate probability for human classifications.
        observationTags: Tag(s) associated with the observation. Formatted as a pipe (`|`) separated list for multiple
            values, with values optionally formatted as `key:value` pairs.
        observationComments: Comments or notes about the observation.

    """
    observationID: str
    """Unique identifier of the observation."""
    deploymentID: str
    """Identifier of the deployment the observation belongs to. Foreign key to `deployments.deploymentID`."""
    mediaID: str | None = None
    """Identifier of the media file that was classified. Only applicable for media-based observations
    (`observationLevel` = `media`). Foreign key to `media.mediaID`."""
    eventID: str | None = None
    """Identifier of the event the observation belongs to. Facilitates linking event-based and media-based
    observations with a permanent identifier."""
    eventStart: IsoTimestamp
    """Date and time at which the event started. Formatted as an ISO 8601 string with timezone designator
    (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`)."""
    eventEnd: IsoTimestamp
    """Date and time at which the event ended. Formatted as an ISO 8601 string with timezone designator
    (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`)."""
    observationLevel: Literal["media", "event"]
    """Level at which the observation was classified. `media` for media-based observations that are
    directly associated with a media file (`mediaID`). These are especially useful for machine
    learning and don't need to be mutually exclusive (e.g. multiple classifications are allowed).
    `event` for event-based observations that consider an event (comprising a collection of media
    files). These are especially useful for ecological research and should be mutually exclusive, so
    that their `count` can be summed."""
    observationType: Literal["animal", "human", "vehicle", "blank", "unknown", "unclassified"]
    """Type of the observation. All categories in this vocabulary have to be understandable from an AI
    point of view. `unknown` describes classifications with a `classificationProbability` below some
    predefined threshold i.e. neither humans nor AI can say what was recorded."""
    cameraSetupType: Literal["setup", "calibration"] | None = None
    """Type of the camera setup action (if any) associated with the observation."""
    scientificName: str | None = None
    """Scientific name of the observed individual(s)."""
    count: Annotated[int | None, Field(ge=1)] = None
    """Number of observed individuals (optionally of given life stage, sex and behavior)."""
    lifeStage: Literal["adult", "subadult", "juvenile"] | None = None
    """Age class or life stage of the observed individual(s)."""
    sex: Literal["female", "male"] | None = None
    """Sex of the observed individual(s)"""
    behavior: str | None = None
    """Dominant behavior of the observed individual(s), preferably expressed as controlled values (e.g.
    grazing, browsing, rooting, vigilance, running, walking). Formatted as a pipe (`|`) separated
    list for multiple values, with the dominant behavior listed first."""
    individualID: str | None = None
    """Identifier of the observed individual."""
    individualPositionRadius: Annotated[float | None, Field(ge=0)] = None
    """Distance from the camera to the observed individual identified by `individualID`. Expressed in
    meters. Required for distance analyses (e.g. [Howe et al.
    2017](https://doi.org/10.1111/2041-210X.12790)) and random encounter modelling (e.g. [Rowcliffe
    et al. 2011](https://doi.org/10.1111/j.2041-210X.2011.00094.x))."""
    individualPositionAngle: Annotated[float | None, Field(ge=-90, le=90)] = None
    """Angular distance from the camera view centerline to the observed individual identified by
    `individualID`. Expressed in degrees, with negative values left, `0` straight ahead and positive
    values right. Required for distance analyses (e.g. [Howe et al.
    2017](https://doi.org/10.1111/2041-210X.12790)) and random encounter modelling (e.g. [Rowcliffe
    et al. 2011](https://doi.org/10.1111/j.2041-210X.2011.00094.x))."""
    individualSpeed: Annotated[float | None, Field(ge=0)] = None
    """Average movement speed of the observed individual identified by `individualID`. Expressed in meters
    per second. Required for random encounter modelling (e.g. [Rowcliffe et al.
    2016](https://doi.org/10.1002/rse2.17))."""
    bboxX: Annotated[float | None, Field(ge=0, le=1)] = None
    """Horizontal position of the top-left corner of a bounding box that encompasses the observed
    individual(s) in the media file identified by `mediaID`. Or the horizontal position of an object
    in that media file. Measured from the left and relative to media file width."""
    bboxY: Annotated[float | None, Field(ge=0, le=1)] = None
    """Vertical position of the top-left corner of a bounding box that encompasses the observed
    individual(s) in the media file identified by `mediaID`. Or the vertical position of an object
    in that media file. Measured from the top and relative to the media file height."""
    bboxWidth: Annotated[float | None, Field(ge=1e-15, le=1)] = None
    """Width of a bounding box that encompasses the observed individual(s) in the media file identified by
    `mediaID`. Measured from the left of the bounding box and relative to the media file width."""
    bboxHeight: Annotated[float | None, Field(ge=1e-15, le=1)] = None
    """Height of the bounding box that encompasses the observed individual(s) in the media file identified
    by `mediaID`. Measured from the top of the bounding box and relative to the media file height."""
    classificationMethod: Literal["human", "machine"] | None = None
    """Method (most recently) used to classify the observation."""
    classifiedBy: str | None = None
    """Name or identifier of the person or AI algorithm that (most recently) classified the observation."""
    classificationTimestamp: IsoTimestamp | None = None
    """Date and time of the (most recent) classification. Formatted as an ISO 8601 string with timezone
    designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`)."""
    classificationProbability: Annotated[float | None, Field(ge=0, le=1)] = None
    """Degree of certainty of the (most recent) classification. Expressed as a probability, with `1` being
    maximum certainty. Omit or provide an approximate probability for human classifications."""
    observationTags: str | None = None
    """Tag(s) associated with the observation. Formatted as a pipe (`|`) separated list for multiple
    values, with values optionally formatted as `key:value` pairs."""
    observationComments: str | None = None
    """Comments or notes about the observation."""

class DeploymentTable(AbstractTable[DeploymentRow]):
    """Table with camera trap placements (deployments). Includes `deploymentID`, start, end, location and
    camera setup information.

    Attributes:
        deploymentID: Unique identifier of the deployment.
        locationID: Identifier of the deployment location.
        locationName: Name given to the deployment location.
        latitude: Latitude of the deployment location in decimal degrees, using the WGS84 datum.
        longitude: Longitude of the deployment location in decimal degrees, using the WGS84 datum.
        coordinateUncertainty: Horizontal distance from the given `latitude` and `longitude` describing the smallest circle
            containing the deployment location. Expressed in meters. Especially relevant when
            coordinates are rounded to protect sensitive species.
        deploymentStart: Date and time at which the deployment was started. Formatted as an ISO 8601 string with timezone
            designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        deploymentEnd: Date and time at which the deployment was ended. Formatted as an ISO 8601 string with timezone
            designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        setupBy: Name or identifier of the person or organization that deployed the camera.
        cameraID: Identifier of the camera used for the deployment (e.g. the camera device serial number).
        cameraModel: Manufacturer and model of the camera. Formatted as `manufacturer-model`.
        cameraDelay: Predefined duration after detection when further activity is ignored. Expressed in seconds.
        cameraHeight: Height at which the camera was deployed. Expressed in meters. Not to be combined with `cameraDepth`.
        cameraDepth: Depth at which the camera was deployed. Expressed in meters. Not to be combined with `cameraHeight`.
        cameraTilt: Angle at which the camera was deployed in the vertical plane. Expressed in degrees, with `-90`
            facing down, `0` horizontal and `90` facing up.
        cameraHeading: Angle at which the camera was deployed in the horizontal plane. Expressed in decimal degrees
            clockwise from north, with values ranging from `0` to `360`: `0` = north, `90` = east,
            `180` = south, `270` = west.
        detectionDistance: Maximum distance at which the camera can reliably detect activity. Expressed in meters. Typically
            measured by having a human move in front of the camera.
        timestampIssues: `true` if timestamps in the `media` resource for the deployment are known to have (unsolvable)
            issues (e.g. unknown timezone, am/pm switch).
        baitUse: `true` if bait was used for the deployment. More information can be provided in `tags` or
            `comments`.
        featureType: Type of the feature (if any) associated with the deployment.
        habitat: Short characterization of the habitat at the deployment location.
        deploymentGroups: Deployment group(s) associated with the deployment. Deployment groups can have a spatial (arrays,
            grids, clusters), temporal (sessions, seasons, months, years) or other context.
            Formatted as a pipe (`|`) separated list for multiple values, with values preferably
            formatted as `key:value` pairs.
        deploymentTags: Tag(s) associated with the deployment. Formatted as a pipe (`|`) separated list for multiple values,
            with values optionally formatted as `key:value` pairs.
        deploymentComments: Comments or notes about the deployment.

    """
    @property
    def unique_fields(self):
        return ("deploymentID",)

    @classmethod
    def get_row_cls(self):
        return DeploymentRow

    def save(self, dir: str = ".", **kwargs):
        path = os.path.join(dir, "deployments.csv")
        return self.to_csv(path, **kwargs)

class MediaTable(AbstractTable[MediaRow]):
    """Table with media files (images/videos) recorded during deployments (`deploymentID`). Includes
    timestamp and file path.

    Attributes:
        mediaID: Unique identifier of the media file.
        deploymentID: Identifier of the deployment the media file belongs to. Foreign key to `deployments.deploymentID`.
        captureMethod: Method used to capture the media file.
        timestamp: Date and time at which the media file was recorded. Formatted as an ISO 8601 string with timezone
            designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        filePath: URL or relative path to the media file, respectively for externally hosted files or files that are
            part of the package.
        filePublic: `false` if the media file is not publicly accessible (e.g. to protect the privacy of people).
        fileName: Name of the media file. If provided, one should be able to sort media files chronologically within a
            deployment on `timestamp` (first) and `fileName` (second).
        fileMediatype: Mediatype of the media file. Expressed as an [IANA Media
            Type](https://www.iana.org/assignments/media-types/media-types.xhtml).
        exifData: EXIF data of the media file. Formatted as a valid JSON object.
        favorite: `true` if the media file is deemed of interest (e.g. an exemplar image of an individual).
        mediaComments: Comments or notes about the media file.

    """
    @property
    def unique_fields(self):
        return ("mediaID",)

    @classmethod
    def get_row_cls(self):
        return MediaRow

    def save(self, dir: str = ".", **kwargs):
        path = os.path.join(dir, "media.csv")
        return self.to_csv(path, **kwargs)

class ObservationsTable(AbstractTable[ObservationsRow]):
    """Table with observations derived from the media files. Associated with deployments (`deploymentID`).
    Observations can mark non-animal events (camera setup, human, blank) or one or more animal
    observations (`observationType` = `animal`) of a certain taxon, count, life stage, sex, behavior
    and/or individual. Observations can be made at different levels (`observationLevel`).

    Attributes:
        observationID: Unique identifier of the observation.
        deploymentID: Identifier of the deployment the observation belongs to. Foreign key to `deployments.deploymentID`.
        mediaID: Identifier of the media file that was classified. Only applicable for media-based observations
            (`observationLevel` = `media`). Foreign key to `media.mediaID`.
        eventID: Identifier of the event the observation belongs to. Facilitates linking event-based and media-based
            observations with a permanent identifier.
        eventStart: Date and time at which the event started. Formatted as an ISO 8601 string with timezone designator
            (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        eventEnd: Date and time at which the event ended. Formatted as an ISO 8601 string with timezone designator
            (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        observationLevel: Level at which the observation was classified. `media` for media-based observations that are
            directly associated with a media file (`mediaID`). These are especially useful for
            machine learning and don't need to be mutually exclusive (e.g. multiple classifications
            are allowed). `event` for event-based observations that consider an event (comprising a
            collection of media files). These are especially useful for ecological research and
            should be mutually exclusive, so that their `count` can be summed.
        observationType: Type of the observation. All categories in this vocabulary have to be understandable from an AI
            point of view. `unknown` describes classifications with a `classificationProbability`
            below some predefined threshold i.e. neither humans nor AI can say what was recorded.
        cameraSetupType: Type of the camera setup action (if any) associated with the observation.
        scientificName: Scientific name of the observed individual(s).
        count: Number of observed individuals (optionally of given life stage, sex and behavior).
        lifeStage: Age class or life stage of the observed individual(s).
        sex: Sex of the observed individual(s)
        behavior: Dominant behavior of the observed individual(s), preferably expressed as controlled values (e.g.
            grazing, browsing, rooting, vigilance, running, walking). Formatted as a pipe (`|`)
            separated list for multiple values, with the dominant behavior listed first.
        individualID: Identifier of the observed individual.
        individualPositionRadius: Distance from the camera to the observed individual identified by `individualID`. Expressed in
            meters. Required for distance analyses (e.g. [Howe et al.
            2017](https://doi.org/10.1111/2041-210X.12790)) and random encounter modelling (e.g.
            [Rowcliffe et al. 2011](https://doi.org/10.1111/j.2041-210X.2011.00094.x)).
        individualPositionAngle: Angular distance from the camera view centerline to the observed individual identified by
            `individualID`. Expressed in degrees, with negative values left, `0` straight ahead and
            positive values right. Required for distance analyses (e.g. [Howe et al.
            2017](https://doi.org/10.1111/2041-210X.12790)) and random encounter modelling (e.g.
            [Rowcliffe et al. 2011](https://doi.org/10.1111/j.2041-210X.2011.00094.x)).
        individualSpeed: Average movement speed of the observed individual identified by `individualID`. Expressed in meters
            per second. Required for random encounter modelling (e.g. [Rowcliffe et al.
            2016](https://doi.org/10.1002/rse2.17)).
        bboxX: Horizontal position of the top-left corner of a bounding box that encompasses the observed
            individual(s) in the media file identified by `mediaID`. Or the horizontal position of
            an object in that media file. Measured from the left and relative to media file width.
        bboxY: Vertical position of the top-left corner of a bounding box that encompasses the observed
            individual(s) in the media file identified by `mediaID`. Or the vertical position of an
            object in that media file. Measured from the top and relative to the media file height.
        bboxWidth: Width of a bounding box that encompasses the observed individual(s) in the media file identified by
            `mediaID`. Measured from the left of the bounding box and relative to the media file
            width.
        bboxHeight: Height of the bounding box that encompasses the observed individual(s) in the media file identified
            by `mediaID`. Measured from the top of the bounding box and relative to the media file
            height.
        classificationMethod: Method (most recently) used to classify the observation.
        classifiedBy: Name or identifier of the person or AI algorithm that (most recently) classified the observation.
        classificationTimestamp: Date and time of the (most recent) classification. Formatted as an ISO 8601 string with timezone
            designator (`YYYY-MM-DDThh:mm:ssZ` or `YYYY-MM-DDThh:mm:ss±hh:mm`).
        classificationProbability: Degree of certainty of the (most recent) classification. Expressed as a probability, with `1` being
            maximum certainty. Omit or provide an approximate probability for human classifications.
        observationTags: Tag(s) associated with the observation. Formatted as a pipe (`|`) separated list for multiple
            values, with values optionally formatted as `key:value` pairs.
        observationComments: Comments or notes about the observation.

    """
    @property
    def unique_fields(self):
        return ("observationID",)

    @classmethod
    def get_row_cls(self):
        return ObservationsRow

    def save(self, dir: str = ".", **kwargs):
        path = os.path.join(dir, "observations.csv")
        return self.to_csv(path, **kwargs)


TABLE_TYPES: dict[str, type[AbstractTable]] = {
    "deployments.csv": DeploymentTable,
    "media.csv": MediaTable,
    "observations.csv": ObservationsTable,
}


def to_table(type: str, **kwargs):
    cls: type[AbstractTable] = TABLE_TYPES[type]
    return cls(**kwargs)
