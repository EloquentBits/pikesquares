import structlog
from sqlmodel import Field, Relationship
from aiopath import AsyncPath

from .base import ServiceBase
from pikesquares.presets.project import ProjectSection


logger = structlog.getLogger()


class Project(ServiceBase, table=True):

    __tablename__ = "projects"

    name: str = Field(default="sandbox", max_length=32)
    device_id: str | None = Field(default=None, foreign_key="devices.id")
    device: "Device" = Relationship(back_populates="projects")
    wsgi_apps: list["WsgiApp"] = Relationship(back_populates="project")
    http_routers: list["HttpRouter"] = Relationship(back_populates="project")
    zmq_monitor: "ZMQMonitor" = Relationship(back_populates="project", sa_relationship_kwargs={"uselist": False})
    tuntap_routers: list["TuntapRouter"] = Relationship(back_populates="project")


    def __repr__(self):
        return f'<{self.handler_name} name="{self.name}" id="{self.id}" service_id="{self.service_id}">'

    @property
    def uwsgi_config_section_class(self) -> ProjectSection:
        return ProjectSection

    def ping(self) -> None:
        print("== Project.ping ==")


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
