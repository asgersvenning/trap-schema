import json
import os
import warnings
from dataclasses import dataclass
from typing import Literal

from pydantic import Field, model_validator

from trap_schema.fields import GeoJSONWrapper, IsoTimestamp
from trap_schema.schema import SerializableModel

warnings.filterwarnings(
    "ignore", 
    message='Field name "schema" in "Resource" shadows an attribute in parent', 
    category=UserWarning
)

@dataclass(kw_only=True)
class Resource(SerializableModel):
    """Data Resource.

    Arguments:
        name: Any.
        path: Path or URL to the data file.
        profile: [Profile](https://specs.frictionlessdata.io/profiles/) of the resource.
        format: The file format of this resource.
        encoding: The file encoding of this resource.
        schema: URL of the used Camtrap DP Table Schema version (e.g.
            `https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0/deployments-table-schema.json`).

    """
    name : Literal["deployments", "media", "observations"]
    path : Literal["deployments.csv", "media.csv", "obsevations.csv"]
    """Path or URL to the data file."""
    profile : Literal["tabular-data-resource"]
    """[Profile](https://specs.frictionlessdata.io/profiles/) of the resource."""
    format : Literal["csv"]
    """The file format of this resource."""
    mediaType : Literal["text/csv"]
    encoding : Literal["utf-8"]
    """The file encoding of this resource."""
    schema : Literal["https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/deployments-table-schema.json", "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/media-table-schema.json", "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/observations-table-schema.json"]
    """URL of the used Camtrap DP Table Schema version (e.g.
    `https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0/deployments-table-schema.json`)."""

def get_resource(type : Literal["deployments", "media", "observations"]):
    return Resource(
        name=type,
        path=f"{type}.csv",
        profile="tabular-data-resource",
        format="csv",
        mediaType="text/csv",
        encoding="utf-8",
        schema=f"https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/{type}-table-schema.json"
    )

def standard_resources():
    return [
        get_resource("deployments"),
        get_resource("media"),
        get_resource("observations")
    ]

@dataclass(kw_only=True)
class Contributor(SerializableModel):
    """A contributor to this descriptor.

    Arguments:
        title: A human-readable title.
        path: A fully qualified URL, or a POSIX file path.
        email: An email address.
        role: Role of the contributor. Defaults to `contributor`.
        organization: An organizational affiliation for this contributor.

    """
    title : str
    """A human-readable title."""
    path : str | None=None
    """A fully qualified URL, or a POSIX file path."""
    email : str | None=None
    """An email address."""
    role : Literal["contact", "principalInvestigator", "rightsHolder", "publisher", "contributor"] | None=None
    """Role of the contributor. Defaults to `contributor`."""
    organization : str | None=None
    """An organizational affiliation for this contributor."""

@dataclass(kw_only=True)
class Source(SerializableModel):
    """A source file.

    Arguments:
        title: A human-readable title.
        path: A fully qualified URL, or a POSIX file path.
        email: An email address.
        version: Version of the source.

    """
    title : str
    """A human-readable title."""
    path : str | None=None
    """A fully qualified URL, or a POSIX file path."""
    email : str | None=None
    """An email address."""
    version : str | None=None
    """Version of the source."""

@dataclass(kw_only=True)
class License(SerializableModel):
    """A license for this descriptor.

    Arguments:
        name: MUST be an Open Definition license identifier, see http://licenses.opendefinition.org/
        path: A fully qualified URL, or a POSIX file path.
        title: A human-readable title.
        scope: Scope of the license. `data` applies to the content of the package and resources, `media` to the
            (locally or externally hosted) media files referenced in `media.filePath`.

    """
    name : str | None=None
    """MUST be an Open Definition license identifier, see http://licenses.opendefinition.org/"""
    path : str | None=None
    """A fully qualified URL, or a POSIX file path."""
    title : str | None=None
    """A human-readable title."""
    scope : Literal["data", "media"]
    """Scope of the license. `data` applies to the content of the package and resources, `media` to the
    (locally or externally hosted) media files referenced in `media.filePath`."""

    @model_validator(mode="after")
    def has_descriptor(self):
        if self.name is None and self.path is None:
            raise TypeError('Either `name` or `path` should be specified.')

@dataclass(kw_only=True)
class Project(SerializableModel):
    """Camera trap project or study that originated the package.

    Arguments:
        id: Unique identifier of the project.
        title: Title of the project. Not to be confused with the title of the package (`package.title`).
        acronym: Project acronym.
        description: Description of the project. Preferably formatted as [Markdown](http://commonmark.org/). Not to be
            confused with the description of the package (`package.description`).
        path: Project website.
        samplingDesign: Type of a sampling design/layout. The values are based on [Wearn & Glover-Kapfer
            (2017)](https://doi.org/10.13140/RG.2.2.23409.17767), pages 80-82: `simple random`:
            random distribution of sampling locations; `systematic random`: random distribution of
            sampling locations, but arranged in a regular pattern; `clustered random`: random
            distribution of sampling locations, but clustered in arrays; `experimental`: non-random
            distribution aimed to study an effect, including the before-after control-impact (BACI)
            design; `targeted`: non-random distribution optimized for capturing specific target
            species (often using various bait types); `opportunistic`: opportunistic camera trapping
            (usually with a small number of cameras).
        captureMethod: Method(s) used to capture the media files.
        individualAnimals: `true` if the project includes marked or recognizable individuals. See also
            `observations.individualID`.
        observationLevel: Level at which observations are provided. See also `observations.observationLevel`.

    """
    id : str | None=None
    """Unique identifier of the project."""
    title : str
    """Title of the project. Not to be confused with the title of the package (`package.title`)."""
    acronym : str | None=None
    """Project acronym."""
    description : str | None=None
    """Description of the project. Preferably formatted as [Markdown](http://commonmark.org/). Not to be
    confused with the description of the package (`package.description`)."""
    path : str | None=None
    """Project website."""
    samplingDesign : Literal["simpleRandom", "systematicRandom", "clusteredRandom", "experimental", "targeted", "opportunistic"]
    """Type of a sampling design/layout. The values are based on [Wearn & Glover-Kapfer
    (2017)](https://doi.org/10.13140/RG.2.2.23409.17767), pages 80-82: `simple random`: random
    distribution of sampling locations; `systematic random`: random distribution of sampling
    locations, but arranged in a regular pattern; `clustered random`: random distribution of
    sampling locations, but clustered in arrays; `experimental`: non-random distribution aimed to
    study an effect, including the before-after control-impact (BACI) design; `targeted`: non-random
    distribution optimized for capturing specific target species (often using various bait types);
    `opportunistic`: opportunistic camera trapping (usually with a small number of cameras)."""
    captureMethod : list[Literal["activityDetection", "timeLapse"]]
    """Method(s) used to capture the media files."""
    individualAnimals : bool
    """`true` if the project includes marked or recognizable individuals. See also
    `observations.individualID`."""
    observationLevel : list[Literal["media", "event"]]
    """Level at which observations are provided. See also `observations.observationLevel`."""

@dataclass(kw_only=True)
class Temporal(SerializableModel):
    """Temporal coverage of the package.

    Arguments:
        start: Start date of the first deployment. Formatted as an ISO 8601 string (`YYYY-MM-DD`).
        end: End date of the last (completed) deployment. Formatted as an ISO 8601 string (`YYYY-MM-DD`).

    """
    start : IsoTimestamp
    """Start date of the first deployment. Formatted as an ISO 8601 string (`YYYY-MM-DD`)."""
    end : IsoTimestamp
    """End date of the last (completed) deployment. Formatted as an ISO 8601 string (`YYYY-MM-DD`)."""

@dataclass(kw_only=True)
class Taxonomic(SerializableModel):
    """

    Arguments:
        scientificName: Scientific name of the taxon.
        taxonID: Unique identifier of the taxon. Preferably a global unique identifier issued by an authoritative
            checklist.
        taxonRank: Taxonomic rank of the scientific name.
        vernacularNames: Common or vernacular names of the taxon, as `languageCode: vernacular name` pairs. Language codes
            should follow ISO 693-3 (e.g. `eng` for English).

    """
    scientificName : str
    """Scientific name of the taxon."""
    taxonID : str | None=None
    """Unique identifier of the taxon. Preferably a global unique identifier issued by an authoritative
    checklist."""
    taxonRank : str | None=None
    """Taxonomic rank of the scientific name."""
    vernacularNames : dict[str, str] | None=None
    """Common or vernacular names of the taxon, as `languageCode: vernacular name` pairs. Language codes
    should follow ISO 693-3 (e.g. `eng` for English)."""

@dataclass(kw_only=True)
class RelatedIdentifiers(SerializableModel):
    """Related identifier.

    Arguments:
        relationType: Description of the relationship between the resource (the package) and the related resource.
        relatedIdentifier: Unique identifier of the related resource (e.g. a DOI or URL).
        resourceTypeGeneral: General type of the related resource.
        relatedIdentifierType: Type of the `RelatedIdentifier`.

    """
    relationType : Literal["IsCitedBy", "Cites", "IsSupplementTo", "IsSupplementedBy", "IsContinuedBy", "Continues", "IsNewVersionOf", "IsPreviousVersionOf", "IsPartOf", "HasPart", "IsPublishedIn", "IsReferencedBy", "References", "IsDocumentedBy", "Documents", "IsCompiledBy", "Compiles", "IsVariantFormOf", "IsOriginalFormOf", "IsIdenticalTo", "HasMetadata", "IsMetadataFor", "Reviews", "IsReviewedBy", "IsDerivedFrom", "IsSourceOf", "Describes", "IsDescribedBy", "HasVersion", "IsVersionOf", "Requires", "IsRequiredBy", "Obsoletes", "IsObsoletedBy"]
    """Description of the relationship between the resource (the package) and the related resource."""
    relatedIdentifier : str
    """Unique identifier of the related resource (e.g. a DOI or URL)."""
    resourceTypeGeneral : Literal["Audiovisual", "Book", "BookChapter", "Collection", "ComputationalNotebook", "ConferencePaper", "ConferenceProceeding", "DataPaper", "Dataset", "Dissertation", "Event", "Image", "InteractiveResource", "Journal", "JournalArticle", "Model", "OutputManagementPlan", "PeerReview", "PhysicalObject", "Preprint", "Report", "Service", "Software", "Sound", "Standard", "Text", "Workflow", "Other"] | None=None
    """General type of the related resource."""
    relatedIdentifierType : Literal["ARK", "arXiv", "bibcode", "DOI", "EAN13", "EISSN", "Handle", "IGSN", "ISBN", "ISSN", "ISTC", "LISSN", "LSID", "PMID", "PURL", "UPC", "URL", "URN", "w3id"]
    """Type of the `RelatedIdentifier`."""

@dataclass(kw_only=True)
class DataPackage(SerializableModel):
    """Data Package is a simple specification for data access and delivery.

    Arguments:
        name: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#name).
        id: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#id).
        created: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#created). Camtrap
            DP makes this a required property.
        title: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#title). Not to be
            confused with the title of the project that originated the package
            (`package.project.title`).
        contributors: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#contributors).
            Camtrap DP makes this a required property and restricts `role` values. Can include
            people and organizations.
        description: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#description). Not
            to be confused with the description of the project that originated the package
            (`package.project.description`).
        version: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#version).
        keywords: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#keywords).
        image: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#image).
        homepage: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#homepage).
        sources: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#sources). Can
            include the data management platform from which the package was derived (e.g. Agouti,
            Trapper, Wildlife Insights).
        licenses: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#licenses). If
            provided, Camtrap DP further requires at least a license for the content of the package
            and one for the media files.
        bibliographicCitation: Bibliographic/recommended citation for the package.
        project: Camera trap project or study that originated the package.
        coordinatePrecision: Least precise coordinate precision of the `deployments.latitude` and `deployments.longitude` (e.g.
            `0.01` for coordinates with a precision of 0.01 and 0.001 degree). Especially relevant
            when coordinates have been rounded to protect sensitive species.
        spatial: GeoJSON
        temporal: Temporal coverage of the package.
        taxonomic: Taxonomic coverage of the package, based on the unique `observations.scientificName`.
        relatedIdentifiers: Identifiers of resources related to the package (e.g. papers, project pages, derived datasets, APIs,
            etc.).
        references: List of references related to the package (e.g. references cited in `package.project.description`).
            References preferably include a DOI.

    """
    resources : list[Resource]=Field(default_factory=standard_resources, init=False)
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#resource-
    information). Camtrap DP further requires each object to be a [Tabular Data
    Resource](https://specs.frictionlessdata.io/tabular-data-resource/) with a specific `name` and
    `schema`. See [Data](https://camtrap-dp.tdwg.org/data) for the requirements for those resources."""
    profile : str=Field(default="https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/camtrap-dp-profile.json", init=False)
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#profile). Camtrap
    DP further requires this to be the URL of the used Camtrap DP Profile version (e.g.
    `https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0/camtrap-dp-profile.json`)."""
    name : str | None=None
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#name)."""
    id : str | None=None
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#id)."""
    created : IsoTimestamp
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#created). Camtrap
    DP makes this a required property."""
    title : str | None=None
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#title). Not to be
    confused with the title of the project that originated the package (`package.project.title`)."""
    contributors : list[Contributor]
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#contributors).
    Camtrap DP makes this a required property and restricts `role` values. Can include people and
    organizations."""
    description : str | None=None
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#description). Not
    to be confused with the description of the project that originated the package
    (`package.project.description`)."""
    version : str | None=None
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#version)."""
    keywords : list[str] | None=None
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#keywords)."""
    image : str | None=None
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#image)."""
    homepage : str | None=None
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#homepage)."""
    sources : list[Source] | None=None
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#sources). Can
    include the data management platform from which the package was derived (e.g. Agouti, Trapper,
    Wildlife Insights)."""
    licenses : list[License] | None=None
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#licenses). If
    provided, Camtrap DP further requires at least a license for the content of the package and one
    for the media files."""
    bibliographicCitation : str | None=None
    """Bibliographic/recommended citation for the package."""
    project : Project
    """Camera trap project or study that originated the package."""
    coordinatePrecision : float | None=None
    """Least precise coordinate precision of the `deployments.latitude` and `deployments.longitude` (e.g.
    `0.01` for coordinates with a precision of 0.01 and 0.001 degree). Especially relevant when
    coordinates have been rounded to protect sensitive species."""
    spatial : GeoJSONWrapper
    """GeoJSON"""
    temporal : Temporal
    """Temporal coverage of the package."""
    taxonomic: list[Taxonomic]
    """Taxonomic coverage of the package, based on the unique `observations.scientificName`."""
    relatedIdentifiers : list[RelatedIdentifiers] | None=None
    """Identifiers of resources related to the package (e.g. papers, project pages, derived datasets, APIs,
    etc.)."""
    references : list[str] | None=None
    """List of references related to the package (e.g. references cited in `package.project.description`).
    References preferably include a DOI."""

    def __post_init__(self):
        if self.spatial is not None and type(self.spatial) is not GeoJSONWrapper:
            self.spatial = GeoJSONWrapper(self.spatial)

    def save(self, dir : str="."):
        path = os.path.join(dir, "datapackage.json")
        with open(path, "w") as f:
            json.dump(self.to_dict(), f)