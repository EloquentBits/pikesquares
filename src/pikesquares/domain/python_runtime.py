from pathlib import Path

import structlog
from packaging.version import Version
from sqlmodel import Relationship

from pikesquares.domain.runtime import AppRuntime
from pikesquares.exceptions import UvCommandExecutionError
from pikesquares.hooks.markers import hook_impl
from pikesquares.service_layer.uv import list_installed_python_versions, which_uv

logger = structlog.getLogger()


class PythonAppRuntime(AppRuntime, table=True):
    """Base App Runtime SQL model class."""

    __tablename__ = "python_app_runtimes"

    wsgi_apps: list["WsgiApp"] = Relationship(back_populates="python_app_runtime")

    @classmethod
    def only_installed(cls, uv_bin: Path | None = None):
        """
        if not py_version:
            py_install = max(all_py_installs, key=lambda item: Version(item["version"]))
        else:
            py_install = next(filter(lambda x: x["version"] == py_version, all_py_installs))
        py_version = py_install.get(py_version)
        py_bin_path = Path(py_install.get("path"))
        """
        try:
            return list_installed_python_versions(uv_bin=uv_bin or which_uv(), only_installed=True)
        except UvCommandExecutionError as exc:
            pass

    @classmethod
    def only_downloads(cls, uv_bin: Path | None = None):
        try:
            return list_installed_python_versions(uv_bin=uv_bin or which_uv(), only_downloads=True)
        except UvCommandExecutionError as exc:
            pass

    @classmethod
    def list_all_versions(cls, uv_bin: Path | None = None):
        try:
            return list_installed_python_versions(uv_bin=uv_bin or which_uv())
        except UvCommandExecutionError as exc:
            pass


class PythonRuntimePlugin:
    """
    App Runtime Plugin
    """

    @hook_impl
    def app_runtime_prompt_for_version(self) -> str:
        print("prompt for version")
        return "3.12"
