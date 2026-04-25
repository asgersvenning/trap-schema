import json
import os
from dataclasses import dataclass, field
from typing import Literal

from trap_schema.fields import GeoJSONWrapper, IsoTimestamp
from trap_schema.schema import SerializableModel


@dataclass(kw_only=True)
class Resource(SerializableModel):
    name : Literal["deployments", "media", "observations"]
    path : Literal["deployments.csv", "media.csv", "obsevations.csv"]
    profile : Literal["tabular-data-resource"]
    format : Literal["csv"]
    mediaType : Literal["text/csv"]
    encoding : Literal["utf-8"]
    schema : Literal["https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/deployments-table-schema.json", "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/media-table-schema.json", "https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/observations-table-schema.json"]

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
    title : str
    path : str | None=None
    email : str | None=None
    role : Literal["contact", "principalInvestigator", "rightsHolder", "publisher", "contributor"] | None=None
    organization : str | None=None

@dataclass(kw_only=True)
class Source(SerializableModel):
    title : str
    path : str | None=None
    email : str | None=None
    version : str | None=None

@dataclass(kw_only=True)
class License(SerializableModel):
    name : str | None=None
    path : str | None=None
    title : str | None=None
    scope : Literal["data", "media"]

    def __post_init__(self):
        if self.name is None and self.path is None:
            raise TypeError('Either `name` or `path` should be specified.')

@dataclass(kw_only=True)
class Project(SerializableModel):
    id : str | None=None
    title : str
    acronym : str | None=None
    description : str | None=None
    path : str | None=None
    samplingDesign : Literal["simpleRandom", "systematicRandom", "clusteredRandom", "experimental", "targeted", "opportunistic"]
    captureMethod : list[Literal["activityDetection", "timeLapse"]]
    individualAnimals : bool
    observationLevel : list[Literal["media", "event"]]

@dataclass(kw_only=True)
class Temporal(SerializableModel):
    start : IsoTimestamp
    end : IsoTimestamp

@dataclass(kw_only=True)
class Taxonomic(SerializableModel):
    scientificName : str
    taxonID : str | None=None
    taxonRank : str | None=None
    vernacularNames : dict[str, str] | None=None

@dataclass(kw_only=True)
class RelatedIdentifiers(SerializableModel):
    relationType : Literal["IsCitedBy", "Cites", "IsSupplementTo", "IsSupplementedBy", "IsContinuedBy", "Continues", "IsNewVersionOf", "IsPreviousVersionOf", "IsPartOf", "HasPart", "IsPublishedIn", "IsReferencedBy", "References", "IsDocumentedBy", "Documents", "IsCompiledBy", "Compiles", "IsVariantFormOf", "IsOriginalFormOf", "IsIdenticalTo", "HasMetadata", "IsMetadataFor", "Reviews", "IsReviewedBy", "IsDerivedFrom", "IsSourceOf", "Describes", "IsDescribedBy", "HasVersion", "IsVersionOf", "Requires", "IsRequiredBy", "Obsoletes", "IsObsoletedBy"]
    relatedIdentifier : str
    resourceTypeGeneral : Literal["Audiovisual", "Book", "BookChapter", "Collection", "ComputationalNotebook", "ConferencePaper", "ConferenceProceeding", "DataPaper", "Dataset", "Dissertation", "Event", "Image", "InteractiveResource", "Journal", "JournalArticle", "Model", "OutputManagementPlan", "PeerReview", "PhysicalObject", "Preprint", "Report", "Service", "Software", "Sound", "Standard", "Text", "Workflow", "Other"] | None=None
    relatedIdentifierType : Literal["ARK", "arXiv", "bibcode", "DOI", "EAN13", "EISSN", "Handle", "IGSN", "ISBN", "ISSN", "ISTC", "LISSN", "LSID", "PMID", "PURL", "UPC", "URL", "URN", "w3id"]

@dataclass(kw_only=True)
class DataPackage(SerializableModel):
    """Metadata in Camtrap DP are expressed in a datapackage.json file. 
    It follows the Data Package specifications and includes generic Data Package properties and specific Camtrap DP properties. 
    Properties indicated with * are required (i.e. cannot be empty).
    

    Arguments:
        name: See [Data Package specification](https://specs.frictionlessdata.io/data-package/#name).

    """
    resources : list[Resource]=field(default_factory=standard_resources, init=False)
    """See [Data Package specification](https://specs.frictionlessdata.io/data-package/#resource-information). 
    Camtrap DP further requires each object to be a [Tabular Data Resource](https://specs.frictionlessdata.io/tabular-data-resource/) with a specific `name` and `schema`. 
    See [Data](https://camtrap-dp.tdwg.org/data) for the requirements for those resources.
    """
    profile : str=field(default="https://raw.githubusercontent.com/tdwg/camtrap-dp/1.0.2/camtrap-dp-profile.json", init=False)
    name : str | None=None
    id : str | None=None
    created : IsoTimestamp
    title : str | None=None
    contributors : list[Contributor]
    description : str | None=None
    version : str | None=None
    keywords : list[str] | None=None
    image : str | None=None
    homepage : str | None=None
    sources : list[Source] | None=None
    licenses : list[License] | None=None
    bibliographicCitation : str | None=None
    project : Project
    coordinatePrecision : float | None=None
    spatial : GeoJSONWrapper
    temporal : Temporal
    taxonomic: list[Taxonomic]
    relatedIdentifiers : list[RelatedIdentifiers] | None=None
    references : list[str] | None=None

    def __post_init__(self):
        if self.spatial is not None and type(self.spatial) is not GeoJSONWrapper:
            self.spatial = GeoJSONWrapper(self.spatial)

    def save(self, dir : str="."):
        path = os.path.join(dir, "datapackage.json")
        with open(path, "w") as f:
            json.dump(self.to_dict(), f)