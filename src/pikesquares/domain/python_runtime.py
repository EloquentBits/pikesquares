from pathlib import Path

import pydantic
import structlog
from plumbum import local as pl_local
from plumbum.path.utils import delete as pl_delete
from plumbum.path.utils import move as pl_move
from sqlmodel import Relationship

from pikesquares.domain.runtime import AppRuntime
from pikesquares.exceptions import UvCommandExecutionError
from pikesquares.hooks.markers import hook_impl
from pikesquares.service_layer.uv import (
    build_python_plugin,
    install_python_version,
    list_installed_python_versions,
    uninstall_python_version,
    which_uv,
)

logger = structlog.getLogger()


class VersionParts(pydantic.BaseModel):
    major: int
    minor: int
    patch: int


class PythonRuntimeVersion(pydantic.BaseModel):
    """
    [{'key': 'cpython-3.14.3-linux-x86_64-gnu',
      'version': '3.14.3',
      'version_parts': {'major': 3, 'minor': 14, 'patch': 3},
      'path': '/home/pk/.local/share/uv/python/cpython-3.14-linux-x86_64-gnu/bin/python3.14',
      'symlink': None,
      'url': None,
      'os': 'linux',
      'variant': 'default',
      'implementation': 'cpython',
      'arch': 'x86_64',
      'libc': 'gnu'},
    """

    key: str
    version: str
    version_parts: VersionParts
    path: Path | None = None
    symlink: Path | None = None
    url: pydantic.HttpUrl | None = None
    variant: str
    implementation: str
    arch: str
    libc: str

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def uwsgi_plugin_name(self) -> str:
        return f"{self.implementation}_{self.version.replace('.', '_')}"


class PythonAppRuntime(AppRuntime, table=True):
    """Base App Runtime SQL model class."""

    __tablename__ = "python_app_runtimes"

    wsgi_apps: list["WsgiApp"] = Relationship(back_populates="python_app_runtime")

    @classmethod
    def build_uwsgi_python_plugin(
        cls,
        runtime_version: PythonRuntimeVersion,
        plugins_dir: Path,
        scie_home: Path,
        uv_bin: Path | None = None,
    ) -> Path:
        plugin_path = build_python_plugin(runtime_version, plugins_dir, scie_home, uv_bin=uv_bin)
        if plugin_path.exists():
            pl_move(plugin_path, plugins_dir)
            return plugins_dir / plugin_path.name

    @classmethod
    def install(cls, runtime_version: PythonRuntimeVersion, uv_bin: Path | None = None):
        try:
            install_python_version(runtime_version, uv_bin)
        except UvCommandExecutionError as exc:
            logger.error(exc)

    @classmethod
    def uninstall(cls, runtime_version: PythonRuntimeVersion, plugins_dir: Path, uv_bin: Path | None = None):
        result = uninstall_python_version(runtime_version, uv_bin)

        logger.info(f"removed python {runtime_version.implementation} {runtime_version.version}")
        logger.info(result)

        plugin_path = pl_local.path(plugins_dir).joinpath(f"{runtime_version.uwsgi_plugin_name}_plugin.so")
        if plugin_path.exists():
            pl_delete(plugin_path)

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
