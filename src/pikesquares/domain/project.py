# import shutil
from pathlib import Path

from sqlmodel import Field, Relationship
from cuid import cuid
import pydantic
from aiopath import AsyncPath
import structlog

from .base import ServiceBase
from pikesquares import services
from pikesquares.conf import ensure_system_dir
from pikesquares.presets.project import ProjectSection


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


async def get_or_create_project(
    name: str,
    device,
    context: dict,
    create_kwargs: dict,
) -> Project:
    from pikesquares.service_layer.uow import UnitOfWork

    uow = await services.aget(context, UnitOfWork)
    project = await uow.projects.get_by_name(name)

    if not project:
        uwsgi_plugins = ["emperor_zeromq"]

        project = Project(
            service_id=f"project_{cuid()}",
            name=name,
            device=device,
            uwsgi_plugins=", ".join(uwsgi_plugins),
            **create_kwargs,
        )
        await uow.projects.add(project)
        await uow.commit()
        logger.debug(f"Created {project} ")
    else:
        logger.debug(f"Using existing sandbox project {project}")

    if not await AsyncPath(project.apps_dir).exists():
        await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)

    if project.enable_dir_monitor:
        uwsgi_config = project.write_uwsgi_config()
        logger.debug(f"wrote config to file: {uwsgi_config}")

    return project


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
