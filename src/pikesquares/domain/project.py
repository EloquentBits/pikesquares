import structlog_sentry_logger
from sqlmodel import Field, Relationship

from pikesquares.domain.base import ServiceBase
from pikesquares.domain.device import Device
from pikesquares.domain.managed_services import AttachedDaemon
from pikesquares.domain.wsgi_app import WsgiApp
from pikesquares.presets.project import ProjectSection
from pikesquares.services.data import EmperorStats

logger = structlog_sentry_logger.getLogger()


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

    def is_running(self):
        try:
            vassals = EmperorStats(**self.device.read_stats()).vassals
            stats = next(filter(lambda v: v.id.split(".ini")[0] == self.service_id, vassals))
            return all([stats.loyal, stats.accepting, stats.loyal])
        except:
            pass

    def is_blacklisted(self):
        try:
            blacklist = EmperorStats(**self.device.read_stats()).blacklist
            blacklist_item = next(filter(lambda v: v.id.split(".ini")[0] == self.service_id, blacklist))
            return bool(blacklist_item)
        except:
            pass
