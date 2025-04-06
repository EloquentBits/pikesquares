from pathlib import Path

import pydantic
import structlog
from sqlmodel import Field, Relationship

from pikesquares.presets.wsgi_app import WsgiAppSection
from pikesquares.services.apps.django import PythonRuntimeDjango

from .base import ServiceBase

logger = structlog.getLogger()


class Router(pydantic.BaseModel):
    router_id: str
    subscription_server_address: str
    app_name: str

    @pydantic.computed_field
    def subscription_server_port(self) -> int:
        try:
            return int(self.subscription_server_address.split(":")[-1])
        except IndexError:
            return 0

    @pydantic.computed_field
    def subscription_server_key(self) -> str:
        # return f"{self.app_name}.pikesquares.dev:{self.subscription_server_port}"
        logger.debug("subscription_server_key")
        return f"{self.app_name}.pikesquares.dev"

    @pydantic.computed_field
    def subscription_server_protocol(self) -> str:
        return "http" if str(self.subscription_server_port).startswith("9") else "https"


class VirtualHost(pydantic.BaseModel):
    address: str
    certificate_path: Path
    certificate_key: Path
    server_names: list[str]
    protocol: str = "https"
    static_files_mapping: dict = {}

    @property
    def is_https(self):
        return all([self.certificate_key, self.certificate_path])


"""
class WsgiAppOptions(pydantic.BaseModel):
    root_dir: Path
    pyvenv_dir: Path
    wsgi_file: Path
    wsgi_module: str
    routers: list[Router] = []
    project_id: str
    workers: int = 3
"""


class WsgiApp(ServiceBase, table=True):

    name: str = Field(max_length=32)

    project_id: str | None = Field(default=None, foreign_key="project.id")
    project: "Project" = Relationship(back_populates="wsgi_apps")

    root_dir: str = Field(max_length=255)
    pyvenv_dir: str = Field(max_length=255)
    wsgi_file: str = Field(max_length=255)
    wsgi_module: str = Field(max_length=50)
    project_id: str = Field(max_length=50)
    workers: int = Field(default=1)
    threads: int = Field(default=1)

    # routers: list["BaseRouter"] = Relationship(back_populates="device")

    # app_options: WsgiAppOptions

    # virtual_hosts: list[VirtualHost] = []
    # zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    @property
    def uwsgi_config_section_class(self) -> WsgiAppSection:
        return WsgiAppSection

    @pydantic.computed_field
    @property
    def service_config(self) -> Path:
        # service_config_dir = self.ensure_system_dir(
        #    Path(self.config_dir) / "projects"
        # )
        # return service_config_dir / f"{self.service_id}.ini"

        return Path(self.conf.config_dir) / f"{self.app_options.project_id}" / "apps" / f"{self.service_id}.ini"

    @pydantic.computed_field
    @property
    def apps_dir(self) -> Path:
        return Path(self.config_dir) / f"{self.service_id}" / "apps"

    def ping(self) -> None:
        logger.debug("== WsgiApp.ping ==")
