import structlog
from sqlmodel import Relationship

logger = structlog.getLogger()

from pikesquares.domain.runtime import AppRuntime, hook_impl


class PythonAppRuntime(AppRuntime, table=True):
    """Base App Runtime SQL model class."""

    __tablename__ = "python_app_runtimes"

    wsgi_apps: list["WsgiApp"] = Relationship(back_populates="python_app_runtime")


class PythonRuntimePlugin:
    """
    App Runtime Plugin
    """

    @hook_impl
    def prompt_for_version(self) -> str:
        print("prompt for version")
        return "3.12"

