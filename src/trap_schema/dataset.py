import os
from pathlib import Path

from pydantic import BaseModel

from trap_schema.base import AbstractContent
from trap_schema.datapackage import DataPackage
from trap_schema.tables import DeploymentsTable, MediaTable, ObservationsTable


class Dataset(BaseModel):
    """
    A Camtrap DP 1.0.2 dataset following https://camtrap-dp.tdwg.org/.

    Arguments:
        datapackage: Metadata about the data package and camera trap project (`datapackage.json`).
        deployments: Table with camera trap placements (deployments) (`deployments.csv`).
        media: Table with media files recorded during deployments (`media.csv`).
        observations: Table with observations derived from the media files (`observations.csv`).
    """
    datapackage: DataPackage
    deployments: DeploymentsTable
    media: MediaTable
    observations: ObservationsTable

    @classmethod
    def load(cls, dir: str | Path = "."):
        dir_path = Path(dir).resolve()
        
        contents : dict[str, AbstractContent] = {}
        for name, field_info in cls.model_fields.items():
            content_cls = field_info.annotation
            assert issubclass(content_cls, AbstractContent)
            contents[name] = content_cls.load(dir_path)
            
        return cls(**contents)

    def save(self, dir: str | Path = "."):
        dir_path = Path(dir).resolve()
        os.makedirs(dir_path, exist_ok=True)
        
        saved_paths : dict[str, Path] = {}
        for name in type(self).model_fields.keys():
            content = getattr(self, name)
            assert isinstance(content, AbstractContent)
            saved_paths[name] = content.save(dir_path)
            
        return saved_paths