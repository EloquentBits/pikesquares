# import shutil
from pathlib import Path

import pydantic
import structlog
from sqlmodel import Field, Relationship

from pikesquares.conf import ensure_system_dir
from pikesquares.presets.project import ProjectSection

from .base import ServiceBase

logger = structlog.getLogger()


class Project(ServiceBase, table=True):

    name: str = Field(default="sandbox", max_length=32)
    device_id: str | None = Field(default=None, foreign_key="device.id")
    device: "Device" = Relationship(back_populates="projects")
    monitor_zmq_ip: str | None = Field(default="127.0.0.1", max_length=50)
    monitor_zmq_port: int | None = Field(default=5252)

    enable_dir_monitor: bool = False
    enable_zeromq_monitor: bool = False

    @property
    def uwsgi_config_section_class(self) -> ProjectSection:
        return ProjectSection

    @pydantic.computed_field
    @property
    def service_config(self) -> Path:
        service_config_dir = ensure_system_dir(Path(self.config_dir) / "projects")
        return service_config_dir / f"{self.service_id}.ini"

    @pydantic.computed_field
    @property
    def apps_dir(self) -> Path:
        return Path(self.config_dir) / f"{self.service_id}" / "apps"

    def ping(self) -> None:
        print("== Project.ping ==")

    @pydantic.computed_field
    @property
    def zeromq_monitor_address(self) -> str:
        return f"zmq://tcp://{self.monitor_zmq_ip}:{self.monitor_zmq_port}"


# SandboxProject = NewType("SandboxProject", Project)

"""
def register_project(
    context,
    project_class,
    service_id,
    conf: AppConfig,
    db: TinyDB
    ):
    def project_factory():
        kwargs = {
            "conf": conf,
            "db": db,
            "service_id": service_id,
        }
        return project_class(**kwargs)
    register_factory(context, project_class, project_factory)


def register_sandbox_project(
    context: dict,
    proj_type: SandboxProject,
    proj_class: Project,
    conf: AppConfig,
    db: TinyDB,
    build_config_on_init: bool | None,
    ) -> None:
    def sandbox_project_factory():
        return proj_class(
            conf=conf,
            db=db,
            service_id="project_sandbox",
            build_config_on_init=build_config_on_init,
        )
    register_factory(context, proj_type, sandbox_project_factory)
"""
