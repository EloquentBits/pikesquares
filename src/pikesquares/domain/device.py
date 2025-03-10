import os
import shutil
from pathlib import Path
import sys
from functools import cached_property

from sqlmodel import Field
import pydantic

import structlog

from .base import ServiceBase


from pikesquares.exceptions import StatsReadError
from pikesquares.presets.device import DeviceSection
from pikesquares.presets import Section
from pikesquares.services.data import DeviceStats
from pikesquares.services.mixins.pki import DevicePKIMixin


logger = structlog.getLogger()


class Device(ServiceBase, DevicePKIMixin, table=True):

    machine_id: str = Field(default=None, unique=True, max_length=32)
    server_run_as_uid: str = Field(default="root")
    server_run_as_gid: str = Field(default="root")

    @pydantic.computed_field
    @cached_property
    def apps_dir(self) -> Path:
        return Path(self.config_dir) / "projects"

    @pydantic.computed_field
    def stats(self) -> DeviceStats | None:
        try:
            return DeviceStats(
                **Device.read_stats(self.stats_address)
            )
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


# class DeviceCreate(Device):
#    pass
