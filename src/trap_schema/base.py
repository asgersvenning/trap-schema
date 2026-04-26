from pathlib import Path

from pydantic import BaseModel


class AbstractContent(BaseModel):
    @classmethod
    def file_name(cls) -> str:
        raise NotImplementedError(f'`{cls.__name__}.file_name() -> str` is not implemented.')

    @classmethod
    def file_path(cls, path_or_dir : str | Path):
        if isinstance(path_or_dir, str):
            path_or_dir = Path(path_or_dir)
        path_or_dir = path_or_dir.resolve()
        if not path_or_dir.is_dir():
            return path_or_dir 
        return path_or_dir / cls.file_name()
    
    @classmethod
    def load[C](cls : C, path : str | Path, **kwargs) -> C:
        """This should be a short wrapper like:
        ```
        def save(self, dir: str | Path = ".", **kwargs):
            return self.from_table(self.file_path(dir), **kwargs)
        ```
        or
        ```
        def save(self, dir: str | Path = ".", **kwargs):
            return self.from_json(self.file_path(dir), **kwargs)
        ```
        """
        raise NotImplementedError(f'{cls.__name__}.load() -> {cls.__name__}')


    def save(self, dir: str | Path = ".", **kwargs) -> Path:
        """This should be a short wrapper like:
        ```
        def save(self, dir: str | Path = ".", **kwargs):
            return self.to_csv(self.file_path(dir), **kwargs)
        ```
        or
        ```
        def save(self, dir: str | Path = ".", **kwargs):
            return self.to_json(self.file_path(dir), **kwargs)
        ```
        """
        raise NotImplementedError(f'{type(self).__name__}.load() -> {type(self).__name__}')
        