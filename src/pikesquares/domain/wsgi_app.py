from pathlib import Path

import pydantic
import structlog
from sqlmodel import Field, Relationship

from pikesquares.hooks.markers import hook_impl
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
        return f"{self.app_name}.pikesquares.local"

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


class WsgiApp(ServiceBase, table=True):

    __tablename__ = "python_wsgi_apps"

    name: str = Field(max_length=32)

    project_id: str | None = Field(default=None, foreign_key="projects.id")
    project: "Project" = Relationship(back_populates="wsgi_apps")

    python_app_runtime_id: str | None = Field(default=None, foreign_key="python_app_runtimes.id")
    python_app_runtime: "PythonAppRuntime" = Relationship(back_populates="wsgi_apps")

    python_app_codebase_id: str | None = Field(default=None, foreign_key="python_app_codebases.id")
    python_app_codebase: "PythonAppCodebase" = Relationship(back_populates="wsgi_apps")

    root_dir: str = Field(max_length=255)
    wsgi_file: str = Field(max_length=255)
    wsgi_module: str = Field(max_length=50)
    venv_dir: str = Field(max_length=255)
    workers: int = Field(default=1)
    threads: int = Field(default=1)

    @pydantic.computed_field
    # routers: list["BaseRouter"] = Relationship(back_populates="device")

    # app_options: WsgiAppOptions

    # virtual_hosts: list[VirtualHost] = []
    # zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    @property
    def uwsgi_config_section_class(self) -> WsgiAppSection:
        return WsgiAppSection

    async def up(self, wsgi_app_device, subscription_server_address, tuntap_router, project_zmq_monitor):
        from pikesquares.service_layer.handlers.monitors import create_or_restart_instance

        section = WsgiAppSection(self)
        section._set("jailed", "true")
        router_tuntap = section.routing.routers.tuntap().device_connect(
            device_name=wsgi_app_device.name,
            socket=tuntap_router.socket,
        )
        #.device_add_rule(
        #    direction="in",
        #    action="route",
        #    src=tuntap_router.ip,
        #    dst=http_router_tuntap_device.ip,
        #    target="10.20.30.40:5060",
        #)
        section.routing.use_router(router_tuntap)

        #; bring up loopback
        #exec-as-root = ifconfig lo up
        section.main_process.run_command_on_event(
            command="ifconfig lo up",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        # bring up interface uwsgi0
        #exec-as-root = ifconfig uwsgi0 192.168.0.2 netmask 255.255.255.0 up
        section.main_process.run_command_on_event(
            command=f"ifconfig {wsgi_app_device.name} {wsgi_app_device.ip} netmask {wsgi_app_device.netmask} up",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        # and set the default gateway
        #exec-as-root = route add default gw 192.168.0.1
        section.main_process.run_command_on_event(
            command=f"route add default gw {tuntap_router.ip}",
            phase=section.main_process.phases.PRIV_DROP_PRE
        )
        section.main_process.run_command_on_event(
            command=f"ping -c 1 {tuntap_router.ip}",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )

        section.subscriptions.subscribe(
            server=subscription_server_address,
            address=str(self.socket_address),  # address and port of wsgi app
            key=f"{self.name}.pikesquares.local" ,
        )
        section.subscriptions.set_server_params(
            client_notify_address=self.subscription_notify_socket,
        )

        print(section.as_configuration().format())
        print(f"launching wsgi app in {project_zmq_monitor.zmq_address}")

        await create_or_restart_instance(
            project_zmq_monitor.zmq_address,
            f"{self.service_id}.ini",
            section.as_configuration().format(do_print=True),
        )
        #await project.zmq_monitor.create_or_restart_instance(f"{wsgi_app.service_id}.ini", wsgi_app, project.zmq_monitor)

    @property
    def subscription_notify_socket(self) -> Path:
        return Path(self.run_dir) / f"{self.service_id}-subscription-notify.sock"

    def ping(self) -> None:
        logger.debug("== WsgiApp.ping ==")
