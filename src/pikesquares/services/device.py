import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

# from cuid import cuid
import pydantic
import typer
from tinydb import TinyDB, Query

#from circus.arbiter import Arbiter
#from circus.pidfile import Pidfile
#from circus.util import check_future_exception_and_log, configure_logger
#from circus import logger

# from uwsgiconf import uwsgi

from pikesquares.conf import ClientConfig
from pikesquares.presets import Section
from pikesquares.presets.device import DeviceSection
from pikesquares.services.base import BaseService
from pikesquares.services import register_factory
from pikesquares.cli.console import console

from .mixins.pki import DevicePKIMixin

__all__ = ("Device",)


class Device(BaseService, DevicePKIMixin):

    config_section_class: Section = DeviceSection
    tiny_db_table: str = "devices"

    @pydantic.computed_field
    def apps_dir(self) -> Path:
        appsdir = Path(self.conf.CONFIG_DIR) / "projects"
        if appsdir and not appsdir.exists():
            appsdir.mkdir(parents=True, exist_ok=True)
        return appsdir

    def stats(self):
        return self.read_stats()

    def up(self):
        self.setup_pki()
        super().up()
        self.sync_db_with_filesystem()

    # self.config_json["uwsgi"]["emperor-wrapper"] = str(
    #    (Path(self.conf.VIRTUAL_ENV) / "bin/uwsgi").resolve()
    # )

    # empjs["uwsgi"]["emperor"] = f"zmq://tcp://{self.conf.EMPEROR_ZMQ_ADDRESS}"
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
        console.info("Starting PikeSquares Server")
        print("!!! Starting PikeSquares Server | pyuwsgi.run !!!")

        pyuwsgi.run(["--json", f"{str(self.service_config.resolve())}"])

    def stop(self):
        if self.get_service_status() == "running":
            self.write_master_fifo("q")

        # res = device_config.main_process.actions.fifo_write(target, command)

    def sync_db_with_filesystem(self):
        config_dir = self.conf.CONFIG_DIR
        if not self.db.table("projects").all():
            for proj_config in (config_dir / "projects").glob("project_*.json"):
                for app_config in (config_dir / proj_config.stem / "apps").glob("*.json"):
                    console.info(f"found loose app config. deleting {app_config.name}")
                    app_config.unlink()
                console.info(f"found loose project config. deleting {proj_config.name}")
                proj_config.unlink()
            # console.info("creating sandbox project.")
            # project_up(conf, "sandbox", f"project_{cuid()}")

        if not self.db.table("routers").all():
            for router_config in (config_dir / "projects").glob("router_*.json"):
                console.info(f"found loose router config. deleting {router_config.name}")
                router_config.unlink()

    def drop_db_tables(self):
        self.db.drop_table("configs")
        self.db.drop_table("device")
        self.db.drop_table("projects")
        self.db.drop_table("routers")
        self.db.drop_table("apps")

    def delete_configs(self):
        config_dir = self.conf.CONFIG_DIR
        for proj_config in (config_dir / "projects").glob("project_*.json"):
            for app_config in (config_dir / proj_config.stem / "apps").glob("*.json"):
                console.info(f"deleting {app_config.name}")
                app_config.unlink()

                # FIXME
                # app_log = self.log_dir / app_config.stem / ".log"
                # app_log.unlink(missing_ok=True)
                # console.info(f"deleting {app_log.name}")

            console.info(f"deleting {proj_config.name}")
            proj_config.unlink()

        for router_config in (config_dir / "projects").glob("router_*.json"):
            console.info(f"found router config. deleting {router_config.name}")
            router_config.unlink()

        for logfile in self.conf.LOG_DIR.glob("*.log"):
            logfile.unlink()

    def uninstall(self, dry_run: bool = False):
        for user_dir in [
            self.conf.DATA_DIR,
            self.conf.CONFIG_DIR,
            self.conf.RUN_DIR,
            self.conf.LOG_DIR,
            self.conf.PLUGINS_DIR,
            self.conf.PKI_DIR,
        ]:
            if not dry_run:
                try:
                    shutil.rmtree(str(user_dir))
                    console.info(f"deleted {str(user_dir)}")
                except FileNotFoundError:
                    pass


def register_device(
    context: dict,
    device_class: Device,
    client_conf: ClientConfig,
    db: TinyDB,
    build_config_on_init: bool | None,
    ) -> None:
    def device_factory():
        data = {
            "conf": client_conf,
            "db": db,
            "service_id": "device",
            "build_config_on_init": build_config_on_init,
        }
        return device_class(**data)
    register_factory(
        context,
        device_class,
        device_factory,
        ping=lambda svc: svc.ping()
    )

# CIRCUS
# def start(self):
#    configure_logger(logger, "debug", "-")

#    circusd_config = self.svc_model.config_dir / "circusd.ini"
#    pidfile = self.svc_model.run_dir / "circusd.pid"
#    arbiter = Arbiter.load_from_config(str(circusd_config))

    # go ahead and set umask early if it is in the config
#    if arbiter.umask is not None:
#        os.umask(arbiter.umask)

#    pidfile = pidfile or arbiter.pidfile or None
#    if pidfile:
#        pidfile = Pidfile(str(pidfile))

#        try:
#            pidfile.create(os.getpid())
#        except RuntimeError as e:
#            print(str(e))
#            sys.exit(1)

    # Main loop
#    restart = True
#    while restart:
#        try:
#            future = arbiter.start()
#            restart = False
#            if check_future_exception_and_log(future) is None:
#                restart = arbiter._restarting
#        except Exception as e:
#            # emergency stop
#            arbiter.loop.run_sync(arbiter._emergency_stop)
#            raise (e)
#        except KeyboardInterrupt:
#            pass
#        finally:
#            arbiter = None
#            # Do not delete pid file if not going to exit
#            if pidfile is not None and restart is False:
#                pidfile.unlink()
