import structlog
from sqlmodel import Field, Relationship

from pikesquares.presets.project import ProjectSection

from .base import ServiceBase
from .device import Device
from .wsgi_app import WsgiApp
from .managed_services import AttachedDaemon

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
    attached_daemons: list["AttachedDaemon"] = Relationship(back_populates="project")

    def __repr__(self):
        return f'<{self.handler_name} name="{self.name}" id="{self.id}" service_id="{self.service_id}">'

    @property
    def uwsgi_config_section_class(self) -> ProjectSection:
        return ProjectSection

    def ping(self) -> None:
        print(f"== {self.__class__.__name__} ping ==")

