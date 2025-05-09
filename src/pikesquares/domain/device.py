import os
import shutil
import sys

# from typing import Any
import uuid
from pathlib import Path

import pydantic
import structlog

# from aiopath import AsyncPath
from sqlmodel import (
    Field,
    Relationship,
    SQLModel,
)

from sqlalchemy import event

from pikesquares.exceptions import StatsReadError
from pikesquares.presets.device import DeviceSection
from pikesquares import services
from pikesquares.services.data import DeviceStats
from pikesquares.services.mixins.pki import DevicePKIMixin

from .base import ServiceBase, TimeStampedBase


logger = structlog.getLogger()


class Device(ServiceBase, DevicePKIMixin, table=True):

    __tablename__ = "devices"

    machine_id: str = Field(default=None, unique=True, max_length=32)
    uwsgi_options: list["DeviceUWSGIOptions"] = Relationship(back_populates="device")
    routers: list["HttpRouter"] = Relationship(back_populates="device")
    projects: list["Project"] = Relationship(back_populates="device")
    zmq_monitor: "ZMQMonitor" = Relationship(back_populates="device", sa_relationship_kwargs={"uselist": False})
    tuntap_routers: list["TuntapRouter"] = Relationship(back_populates="device")

    # def model_post_init(self, __context: Any) -> None:
    #    super().model_post_init(__context)

    # async def delete_config_from_filesystem(self) -> None:
    #   await AsyncPath(self.service_config).unlink()

    @property
    def uwsgi_config_section_class(self) -> DeviceSection:
        return DeviceSection

        """uWSGI Stats Server socket address"""
        return Path(self.run_dir) / f"{self.service_id}-tuntap-stats.sock"

    def stats(self) -> DeviceStats | None:

        if not self.stats_address.exists():
            return

        try:

            device_stats = Device.read_stats(self.stats_address)
            if device_stats:
                return DeviceStats(**device_stats)
        except StatsReadError:
            pass

    # def up(self):
    #    self.setup_pki()

    # self.config_json["uwsgi"]["emperor-wrapper"] = str(
    #    (Path(self.VIRTUAL_ENV) / "bin/uwsgi").resolve()
    # )

    # empjs["uwsgi"]["emperor"] = f"zmq://tcp://{self.EMPEROR_ZMQ_ADDRESS}"
    # config["uwsgi"]["plugin"] = "emperor_zeromq"
    # self.config_json["uwsgi"]["spooler-import"] = "pikesquares.tasks.ensure_up"

    def get_uwsgi_options(self) -> list["DeviceUWSGIOptions"]:
        uwsgi_options: list[DeviceUWSGIOptions] = []
        section = DeviceSection(self)
        section.empire.set_emperor_params(
            vassals_home=self.zmq_monitor.uwsgi_zmq_address,
            name="PikeSquares Server",
            spawn_asap=True,
            stats_address=str(self.stats_address),
        )

        for key, value in section._get_options():
            uwsgi_option = DeviceUWSGIOptions(
                option_key=key.key,
                option_value=str(value).strip(),
                device=self,
            )
            uwsgi_options.append(uwsgi_option)
            uwsgi_option.sort_order_index = uwsgi_options.index(uwsgi_option)

        return uwsgi_options

    def start_pyuwsgi(self) -> bool:
        # we import `pyuwsgi` with `dlopen` flags set to `os.RTLD_GLOBAL` such that
        # uwsgi plugins can discover uwsgi's globals (notably `extern ... uwsgi`)
        if hasattr(sys, "setdlopenflags"):
            orig = sys.getdlopenflags()
            try:
                sys.setdlopenflags(orig | os.RTLD_GLOBAL)
                import pyuwsgi
            finally:
                sys.setdlopenflags(orig)
        else:  # ah well, can't control how dlopen works here
            import pyuwsgi
        logger.info("Starting PikeSquares Server")
        logger.info("!!! Starting PikeSquares Server | pyuwsgi.run !!!")

        pyuwsgi.run(["--json", f"{str(self.service_config.resolve())}"])

    def stop(self):
        if self.get_service_status() == "running":
            self.write_master_fifo("q")

        # res = device_config.main_process.actions.fifo_write(target, command)

    """
    async def sync_db_with_filesystem(self, uow: "UnitOfWork"):

        routers = await uow.routers.get_by_device_id(self.id)
        projects = await uow.projects.get_by_device_id(self.id)
        logger.debug(f"cleaning up stale project configs from filesystem. Found {len(projects)} projects")
        projects_dir = Path(self.config_dir) / "projects"
        project_configs = [str(p.service_config) for p in projects]
        logger.debug(f"{project_configs=}")
        async for proj_config in AsyncPath(projects_dir).glob("project_*.ini"):
            logger.debug(proj_config)
            if str(proj_config) in project_configs:
                continue

            apps_dir = Path(self.config_dir) / proj_config.stem / "apps"
            async for app_config in AsyncPath(apps_dir).glob("*.ini"):
                logger.info(f"found loose app config. deleting {app_config.name}")
                await AsyncPath(app_config).unlink()

            logger.info(f"found loose project config. deleting {proj_config.name}")
            await AsyncPath(proj_config).unlink()

        router_configs = [str(r.service_config) for r in routers]
        logger.debug(f"{router_configs=}")
        async for router_config in AsyncPath(projects_dir).glob("*router_*.ini"):
            logger.debug(router_config)
            if str(router_config) in router_configs:
                continue
            logger.info(f"found loose router config. deleting {router_config.name}")
            await AsyncPath(router_config).unlink()

    def delete_configs(self):
        for proj_config in (self.config_dir / "projects").glob("project_*.ini"):
            for app_config in (self.config_dir / proj_config.stem / "apps").glob("*.ini"):
                logger.info(f"deleting {app_config.name}")
                app_config.unlink()
            logger.info(f"deleting {proj_config.name}")
            proj_config.unlink()

        for router_config in (self.config_dir / "projects").glob("*router_*.ini"):
            logger.info(f"found router config. deleting {router_config.name}")
            router_config.unlink()
    """

    def delete_logs(self):
        if self.log_dir:
            for logfile in self.log_dir.glob("*.log"):
                logfile.unlink()

    def uninstall(self, dry_run: bool = False):
        for user_dir in [
            self.data_dir,
            self.config_dir,
            self.run_dir,
            self.log_dir,
            self.pki_dir,
        ]:
            if not dry_run:
                try:
                    shutil.rmtree(str(user_dir))
                    logger.info(f"deleted {str(user_dir)}")
                except FileNotFoundError:
                    pass


class DeviceUWSGIOptions(TimeStampedBase, SQLModel, table=True):

    __tablename__ = "uwsgi_options"

    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4()),
        max_length=36,
    )
    option_key: str = Field()
    option_value: str = Field()

    device_id: str | None = Field(default=None, foreign_key="devices.id")
    device: Device | None = Relationship(back_populates="uwsgi_options")
    sort_order_index: int | None = Field(default=None)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def __repr__(self):
        return f'<DeviceUWSGIOptions option_key="{self.option_key}" option_value="{self.option_value}">'

    def __str__(self):
        return self.__repr__()


"""
def register_device(
    context: dict,
    ) -> None:

    def device_factory():
        return Device()

    services.register_factory(
        context,
        Device,
        device_factory,
        #ping=lambda svc: svc.ping()
    )
"""


async def ping_device_stats(device_stats: DeviceStats):
    if device_stats:
        logger.debug(f"{device_stats=}")
        return True
    else:
        return False


async def register_device_stats(
    context: dict,
) -> None:

    async def device_stats_factory():
        device = context.get("device")
        if device:
            try:
                return Device.read_stats(device.stats_address)
            except StatsReadError:
                pass

    services.register_factory(
        context,
        DeviceStats,
        device_stats_factory,
        ping=ping_device_stats,
        # ping=lambda svc: svc.ping()
    )


@event.listens_for(Device, "after_insert")
def handle_device_created(
    mapper,
    connection,
    target,
) -> Device:
    device = target
    logger.info(f"DEVICE DEVICE DEVICE {device=}")
    """
    device.zmq_monitor = await uow.zmq_monitors.get_by_device_id(device.id) or await create_zmq_monitor(
        uow, device=device
    )
    # if not uwsgi_options:
    for uwsgi_option in device.get_uwsgi_options():
        await uow.uwsgi_options.add(uwsgi_option)
    """

    """
        existing_options = await uow.uwsgi_options.list(device_id=device.id)
        for uwsgi_option in device.build_uwsgi_options():
            #existing_options
            #if uwsgi_option.option_key
            #not in existing_options:
            #    await uow.uwsgi_options.add(uwsgi_option)
        """


    return device


"""

            network_device_name = "psq0"
            router = RouterTunTap(
                on=str(self.tuntap_router_socket_address),
                device=network_device_name,
                stats_server=str(self.tuntap_router_stats_address),
            )
            router.add_firewall_rule(direction="out", action="allow", src="192.168.0.0/24", dst="192.168.0.1")
            router.add_firewall_rule(direction="out", action="deny", src="192.168.0.0/24", dst="192.168.0.0/24")
            router.add_firewall_rule(direction="out", action="allow", src="192.168.0.0/24", dst="0.0.0.0")
            router.add_firewall_rule(direction="out", action="deny")
            router.add_firewall_rule(direction="in", action="allow", src="192.168.0.1", dst="192.168.0.0/24")
            router.add_firewall_rule(direction="in", action="deny", src="192.168.0.0/24", dst="192.168.0.0/24")
            router.add_firewall_rule(direction="in", action="allow", src="0.0.0.0", dst="192.168.0.0/24")
            router.add_firewall_rule(direction="in", action="deny")
            section.routing.use_router(router)

            # give it an ip address
            section.main_process.run_command_on_event(
                command=f"ifconfig {network_device_name} 192.168.0.1 netmask 255.255.255.0 up",
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
            # force vassals to be created in a new network namespace
            section._set("emperor-use-clone", "net")
        return super().get_uwsgi_config()
"""

