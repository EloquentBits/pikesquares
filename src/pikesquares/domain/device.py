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

from pikesquares.exceptions import StatsReadError
from pikesquares.presets.device import DeviceSection
from pikesquares.services.data import DeviceStats
from pikesquares.services.mixins.pki import DevicePKIMixin

from .base import ServiceBase, TimeStampedBase


logger = structlog.getLogger()


class Device(ServiceBase, DevicePKIMixin, table=True):

    machine_id: str = Field(default=None, unique=True, max_length=32)
    uwsgi_options: list["DeviceUWSGIOptions"] = Relationship(back_populates="device")
    routers: list["BaseRouter"] = Relationship(back_populates="device")
    projects: list["Project"] = Relationship(back_populates="device")

    monitor_zmq_ip: str | None = Field(default="127.0.0.1", max_length=50)
    monitor_zmq_port: int | None = Field(default=5242)

    enable_dir_monitor: bool = False
    enable_zeromq_monitor: bool = False
    enable_tuntap_router: bool = False

    # def model_post_init(self, __context: Any) -> None:
    #    super().model_post_init(__context)

    @pydantic.computed_field
    @property
    def apps_dir(self) -> Path | None:
        if self.enable_dir_monitor:
            return Path(self.config_dir) / "projects"

    @pydantic.computed_field
    @property
    def service_config(self) -> Path | None:
        if self.enable_dir_monitor:
            return Path(self.config_dir) / f"{self.service_id}.ini"

    # async def delete_config_from_filesystem(self) -> None:
    #   await AsyncPath(self.service_config).unlink()

    @pydantic.computed_field
    @property
    def zeromq_monitor_address(self) -> str:
        return f"zmq://tcp://{self.monitor_zmq_ip}:{self.monitor_zmq_port}"

    @property
    def uwsgi_config_section_class(self) -> DeviceSection:
        return DeviceSection

    @pydantic.computed_field
    @property
    def tuntap_router_stats_address(self) -> Path:
        """uWSGI Stats Server socket address"""
        return Path(self.run_dir) / f"{self.service_id}-tuntap-stats.sock"

    @pydantic.computed_field
    @property
    def tuntap_router_socket_address(self) -> Path:
        return Path(self.run_dir) / f"{self.service_id}-tuntap.sock"

    @pydantic.computed_field
    def stats(self) -> DeviceStats | None:

        if not self.stats_address.exists():
            return

        try:

            device_stats = Device.read_stats(self.stats_address)
            if device_stats:
                return DeviceStats(**device_stats)
        except StatsReadError:
            pass

    def up(self):
        self.setup_pki()
        super().up()

    # self.config_json["uwsgi"]["emperor-wrapper"] = str(
    #    (Path(self.VIRTUAL_ENV) / "bin/uwsgi").resolve()
    # )

    # empjs["uwsgi"]["emperor"] = f"zmq://tcp://{self.EMPEROR_ZMQ_ADDRESS}"
    # config["uwsgi"]["plugin"] = "emperor_zeromq"
    # self.config_json["uwsgi"]["spooler-import"] = "pikesquares.tasks.ensure_up"

    def get_uwsgi_options(self) -> list["DeviceUWSGIOptions"]:
        uwsgi_options: list[DeviceUWSGIOptions] = []
        dvc_conf_section = DeviceSection(self)

        for key, value in dvc_conf_section._get_options():
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

    device_id: str | None = Field(default=None, foreign_key="device.id")
    device: Device | None = Relationship(back_populates="uwsgi_options")
    sort_order_index: int | None = Field(default=None)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def __repr__(self):
        return f'<DeviceUWSGIOptions option_key="{self.option_key}" option_value="{self.option_value}">'

    def __str__(self):
        return self.__repr__()
