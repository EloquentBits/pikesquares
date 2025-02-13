from pathlib import Path
from abc import ABC, abstractmethod

import pydantic
from rich.console import RenderableType
import structlog

# from wsgi import WsgiApp

# __all__ = (
#    "WsgiApp",
# )

import logging
LOG_FILE = "app.log"
logging.basicConfig(
    filename=LOG_FILE,  # Log only to a file
    level=logging.DEBUG,  # Set the desired log level
    format="%(message)s",
)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()


class BaseLanguageRuntime(pydantic.BaseModel, ABC):

    MATCH_FILES: set[str]
    app_root_dir: Path
    collected_project_metadata: dict = {}

    def __init_subclass__(cls):
        logger.debug(f"Subclass {cls} was created.")

    @abstractmethod
    def check(self,
        app_tmp_dir: Path,
        console_status: RenderableType | None = None,
        ):
        raise NotImplementedError

    @abstractmethod
    def init(
        self,
        console_status: RenderableType | None = None,
        venv: Path | None = None
        ) -> bool:
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

    def check(self,
        app_tmp_dir: Path,
        console_status: RenderableType | None = None,
        ) -> bool:
        logger.info("Ruby Check")
        return True

    def init(self,
        console_status: RenderableType | None = None,
        venv: Path | None = None
        ) -> bool:
        logger.info("Ruby Init")
        return True


class PHPRuntime(BaseLanguageRuntime):
    MATCH_FILES: set[str] = set({
        "index.php",
    })

    def check(self,
        app_tmp_dir: Path,
        console_status: RenderableType | None = None,
        ):
        pass

    def init(
        self,
        console_status: RenderableType | None = None,
        venv: Path | None = None,
        ):
        pass
