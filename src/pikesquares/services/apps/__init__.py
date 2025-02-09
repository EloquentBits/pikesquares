from pathlib import Path
from abc import ABC, abstractmethod

import pydantic

# from wsgi import WsgiApp

# __all__ = (
#    "WsgiApp",
# )


class BaseLanguageRuntime(pydantic.BaseModel, ABC):

    MATCH_FILES: set[str]
    app_root_dir: Path
    collected_project_metadata: dict | None = None

    def __init_subclass__(cls):
        print(f"Subclass {cls} was created.")

    @abstractmethod
    def check(self):
        raise NotImplementedError

    @abstractmethod
    def init(self, venv: Path | None = None):
        raise NotImplementedError

    def get_files(self) -> set[Path]:
        all_files: set[Path] = set()
        for ext in self.MATCH_FILES:
            try:
                all_files.add(next(Path(self.app_root_dir).glob(ext)))
            except StopIteration:
                continue
        return all_files

    def get_top_level_files(self) -> set[Path]:
        return self.get_files()

    @property
    def top_level_file_names(self) -> set[str]:
        return {f.name for f in self.get_top_level_files()}


class RubyRuntime(BaseLanguageRuntime):
    MATCH_FILES: set[str] = set({
        "config.ru",
        "Gemfile",
    })

    @abstractmethod
    def check(self) -> bool:
        print("Ruby Check")
        return True

    @abstractmethod
    def init(self, venv: Path | None = None) -> bool:
        print("Ruby Init")
        return True


class PHPRuntime(BaseLanguageRuntime):
    MATCH_FILES: set[str] = set({
        "index.php",
    })

    @abstractmethod
    def check(self):
        pass

    @abstractmethod
    def init(self, venv: Path | None = None):
        pass
