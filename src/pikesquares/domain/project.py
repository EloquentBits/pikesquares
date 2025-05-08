# import shutil
from pathlib import Path

import pydantic
import structlog
from sqlmodel import Field, Relationship
from aiopath import AsyncPath

from .base import ServiceBase
from pikesquares.conf import ensure_system_path
from pikesquares.presets.project import ProjectSection


logger = structlog.getLogger()


class Project(ServiceBase, table=True):

    __tablename__ = "projects"

    name: str = Field(default="sandbox", max_length=32)
    device_id: str | None = Field(default=None, foreign_key="devices.id")
    device: "Device" = Relationship(back_populates="projects")
    wsgi_apps: list["WsgiApp"] = Relationship(back_populates="project")
    zmq_monitor: "ZMQMonitor" = Relationship(back_populates="project", sa_relationship_kwargs={"uselist": False})


    def __repr__(self):
        return f'<{self.handler_name} name="{self.name}" id="{self.id}" service_id="{self.service_id}">'

    @property
    def uwsgi_config_section_class(self) -> ProjectSection:
        return ProjectSection

    @pydantic.computed_field
    @property
    def service_config(self) -> Path | None:
        if self.enable_dir_monitor:
            service_config_dir = ensure_system_path(Path(self.config_dir) / "projects")
            return service_config_dir / f"{self.service_id}.ini"

    @pydantic.computed_field
    @property
    def apps_dir(self) -> Path:
        return Path(self.config_dir) / f"{self.service_id}" / "apps"

    async def up(self, vassals_home, tuntap_router):
        from pikesquares.service_layer.handlers.monitors import create_or_restart_instance
        #device_zmq_monitor
        #project_zmq_monitor = project.zmq_monitor
        section = ProjectSection(self)
        section.empire.set_emperor_params(
            vassals_home=vassals_home,
            name=f"{self.service_id}",
            stats_address=self.stats_address,
            spawn_asap=True,
            # pid_file=str((Path(conf.RUN_DIR) / f"{self.service_id}.pid").resolve()),
        )

        router_cls = section.routing.routers.tuntap
        router = router_cls(
            on=tuntap_router.socket,
            device=tuntap_router.name,
            stats_server=str(AsyncPath(
                tuntap_router.run_dir) / f"tuntap-{tuntap_router.name}-stats.sock"
            ),
        )
        router.add_firewall_rule(direction="out", action="allow", src="192.168.34.0/24", dst=tuntap_router.ip)
        router.add_firewall_rule(direction="out", action="deny", src="192.168.34.0/24", dst="192.168.34.0/24")
        router.add_firewall_rule(direction="out", action="allow", src="192.168.34.0/24", dst="0.0.0.0")
        router.add_firewall_rule(direction="out", action="deny")
        router.add_firewall_rule(direction="in", action="allow", src=tuntap_router.ip, dst="192.168.34.0/24")
        router.add_firewall_rule(direction="in", action="deny", src="192.168.34.0/24", dst="192.168.34.0/24")
        router.add_firewall_rule(direction="in", action="allow", src="0.0.0.0", dst="192.168.34.0/24")
        router.add_firewall_rule(direction="in", action="deny")
        section.routing.use_router(router)

        # give it an ip address
        section.main_process.run_command_on_event(
            command=f"ifconfig {tuntap_router.name} {tuntap_router.ip} netmask {tuntap_router.netmask} up",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        # setup nat
        section.main_process.run_command_on_event(
            command="iptables -t nat -F", phase=section.main_process.phases.PRIV_DROP_PRE
        )
        section.main_process.run_command_on_event(
            command="iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        # enable linux ip forwarding
        section.main_process.run_command_on_event(
            command="echo 1 >/proc/sys/net/ipv4/ip_forward",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        section._set("emperor-use-clone", "net")

        print(section.as_configuration().format())
        await create_or_restart_instance(
            vassals_home,
            f"{self.service_id}.ini",
            section.as_configuration().format(do_print=True),
        )

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
