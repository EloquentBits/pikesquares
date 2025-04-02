import os
import shutil
import sys

# from typing import Any
import uuid
from pathlib import Path

import pydantic
import structlog
from cuid import cuid
from sqlmodel import (
    Field,
    Relationship,
    SQLModel,
)

from pikesquares import services
from pikesquares.conf import AppConfigError
from pikesquares.exceptions import StatsReadError
from pikesquares.presets.device import DeviceSection
from pikesquares.services.data import DeviceStats
from pikesquares.services.mixins.pki import DevicePKIMixin
from pikesquares.domain.project import get_or_create_project
from pikesquares.domain.router import get_or_create_http_router

from .base import ServiceBase, TimeStampedBase

logger = structlog.getLogger()


class Device(ServiceBase, DevicePKIMixin, table=True):

    machine_id: str = Field(default=None, unique=True, max_length=32)
    uwsgi_options: list["DeviceUWSGIOptions"] = Relationship(back_populates="device")
    routers: list["BaseRouter"] = Relationship(back_populates="device")

    enable_tuntap_router: bool = False

    # def model_post_init(self, __context: Any) -> None:
    #    super().model_post_init(__context)

    @pydantic.computed_field
    @property
    def apps_dir(self) -> Path:
        return Path(self.config_dir) / "projects"

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
        # self.sync_db_with_filesystem()

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

    def start(self):
        pass

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

    def sync_db_with_filesystem(self):
        config_dir = self.config_dir
        if not self.db.table("projects").all():
            for proj_config in (config_dir / "projects").glob("project_*.json"):
                for app_config in (config_dir / proj_config.stem / "apps").glob("*.json"):
                    logger.info(f"found loose app config. deleting {app_config.name}")
                    app_config.unlink()
                logger.info(f"found loose project config. deleting {proj_config.name}")
                proj_config.unlink()
            # logger.info("creating sandbox project.")
            # project_up(conf, "sandbox", f"project_{cuid()}")

        if not self.db.table("routers").all():
            for router_config in (config_dir / "projects").glob("router_*.json"):
                logger.info(f"found loose router config. deleting {router_config.name}")
                router_config.unlink()

    def delete_configs(self):
        config_dir = self.config_dir
        for proj_config in (config_dir / "projects").glob("project_*.json"):
            for app_config in (config_dir / proj_config.stem / "apps").glob("*.json"):
                logger.info(f"deleting {app_config.name}")
                app_config.unlink()

                # FIXME
                # app_log = self.log_dir / app_config.stem / ".log"
                # app_log.unlink(missing_ok=True)
                # logger.info(f"deleting {app_log.name}")

            logger.info(f"deleting {proj_config.name}")
            proj_config.unlink()

        for router_config in (config_dir / "projects").glob("router_*.json"):
            logger.info(f"found router config. deleting {router_config.name}")
            router_config.unlink()

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


async def get_or_create_device(
    context: dict,
    create_kwargs: dict,
    enable_tuntap_router: bool = False,
) -> Device:
    from pikesquares.service_layer.uow import UnitOfWork

    uow = await services.aget(context, UnitOfWork)
    machine_id = await ServiceBase.read_machine_id()
    if not machine_id:
        raise AppConfigError("unable to read the machine-id")

    device = await uow.devices.get_by_machine_id(machine_id)
    if not device:
        uwsgi_plugins = []
        if enable_tuntap_router:
            uwsgi_plugins.append("tuntap")

        device = Device(
            service_id=f"device_{cuid()}",
            uwsgi_plugins=", ".join(uwsgi_plugins),
            machine_id=machine_id,
            **create_kwargs,
        )
        # device.routers.add(default_http_router)
        device = await uow.devices.add(device)
        await uow.commit()
        logger.debug(f"Created {device=} for {machine_id=}")

    default_http_router = await get_or_create_http_router(
        "default-http-router",
        device,
        context,
        create_kwargs,
    )
    context["default-http-router"] = default_http_router

    default_project = await get_or_create_project("default-project", context, create_kwargs)
    context["default-project"] = default_project

    uwsgi_config = device.write_uwsgi_config()
    logger.debug(f"wrote config to file: {uwsgi_config}")

    return device
