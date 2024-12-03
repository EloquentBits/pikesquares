import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

# from cuid import cuid
import pydantic
import typer
from tinydb import Query

#from circus.arbiter import Arbiter
#from circus.pidfile import Pidfile
#from circus.util import check_future_exception_and_log, configure_logger
#from circus import logger

# from uwsgiconf import uwsgi

from pikesquares import read_stats
from pikesquares.presets import device
from pikesquares.services.base import BaseService
from pikesquares.services import register_factory
from pikesquares.cli.console import console

__all__ = ("Device",)


class Device(BaseService):

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / "device.json"

    @pydantic.computed_field
    def spooler_dir(self) -> Path:
        spdir = Path(self.conf.DATA_DIR) / "spooler"
        if spdir and not spdir.exists():
            spdir.mkdir(parents=True, exist_ok=True)
        return spdir

    @pydantic.computed_field
    def apps_dir(self) -> Path:
        appsdir = Path(self.conf.CONFIG_DIR) / "projects"
        if appsdir and not appsdir.exists():
            appsdir.mkdir(parents=True, exist_ok=True)
        return appsdir

    def stats(self):
        return self.read_stats()

    def up(self):
        # from pikesquares.services import (
        #    Project,
        #    HttpsRouter,
        #    HttpRouter,
        # )
        # conf.DAEMONIZE = not foreground
        self.setup_pki()

        self.prepare_service_config()
        self.save_config()
        self.write_config()

        self.sync_db_with_filesystem()

        # with TinyDB(self.device_db_path) as db:
        #    for project_doc in db.table('projects'):
        #        project_handler = HandlerFactory.make_handler("Project")(
        #            Project(
        #                service_id=project_doc.get("service_id")
        #            )
        #        )
        #        project_handler.up(project_doc.get("name"))

        #    for router_doc in db.table('routers'):
        #        handler_name = None
        #        handler_class = None
        #        if router_doc.get("service_type") == "HttpRouterService":
        #            handler_name = "Http-Router"
        #            handler_class = HttpRouter
        #        elif router_doc.get("service_type") == "HttpRouterService":
        #            handler_name = "Https-Router"
        #            handler_class = HttpsRouter

        #        if all([
        #            handler_name,
        #            handler_name == "Http-Router",
        #            handler_class]):
        #            HandlerFactory.make_handler(handler_name)(
        #                    handler_class(service_id=router_doc.get("service_id")
        #            )).up(router_doc.get("address").split("://")[-1])

        # self.start()

    def start(self):
        pass

    def save_config(self):
        # with TinyDB(self.device_db_path) as db:
        self.db.table("devices").upsert(
            {
                "service_type": self.handler_name,
                "service_config": self.config_json,
            },
            Query().service_type == self.handler_name,
        )

    def prepare_service_config(self):
        config = device.DeviceSection(self)\
                .as_configuration()\
                .format(formatter="json")
        self.config_json = json.loads(config)
        self.config_json["uwsgi"]["show-config"] = True

        # self.config_json["uwsgi"]["emperor-wrapper"] = str(
        #    (Path(self.conf.VIRTUAL_ENV) / "bin/uwsgi").resolve()
        # )

        # empjs["uwsgi"]["emperor"] = f"zmq://tcp://{self.conf.EMPEROR_ZMQ_ADDRESS}"
        # config["uwsgi"]["plugin"] = "emperor_zeromq"
        # self.config_json["uwsgi"]["spooler-import"] = "pikesquares.tasks.ensure_up"

    def connect(self):
        pass

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

    def setup_pki(self):
        if all(
            [
                self.ensure_pki(),
                self.ensure_build_ca(),
                self.ensure_csr(),
                self.ensure_sign_req(),
            ]
        ):
            console.success("Wildcard certificate created.")

    def ensure_pki(self):
        if self.conf.PKI_DIR.exists():
            return

        compl = subprocess.run(
            args=[
                str(self.conf.EASYRSA_BIN),
                "init-pki",
            ],
            cwd=str(self.conf.DATA_DIR),
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to initialize PKI")
        else:
            print(f"Initialized PKI @ {self.conf.PKI_DIR}")
        # set(compl.stdout.decode().split("\n"))

    def ensure_build_ca(self):
        if not self.conf.PKI_DIR.exists():
            print(f"Unable to create CA. PKI was not located.")
            return

        if (self.conf.PKI_DIR / "ca.crt").exists():
            return

        print("building CA")

        compl = subprocess.run(
            args=[
                str(self.conf.EASYRSA_BIN),
                '--req-cn=PikeSquares Proxy',
                "--batch",
                "--no-pass",
                "build-ca",
            ],
            cwd=self.conf.DATA_DIR,
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to build CA")
            print(compl.stderr.decode())
        elif (self.conf.PKI_DIR / "ca.crt").exists():
            print(f"CA cert created")
            print(compl.stdout.decode())

        # set(compl.stdout.decode().split("\n"))

    def ensure_csr(self):
        if not self.conf.PKI_DIR.exists():
            print("Unable to create a CSR. PKI was not located.")
            return

        if not (self.conf.PKI_DIR / "ca.crt").exists():
            print("Unable to create a CSR. CA was not located.")
            return

        if (self.conf.PKI_DIR / "reqs" / f"{self.cert_name}.req").exists():
            return

        print("generating CSR")
        compl = subprocess.run(
            args=[
                str(self.conf.EASYRSA_BIN),
                "--batch",
                "--no-pass",
                "--silent",
                "--subject-alt-name=DNS:*.pikesquares.dev",
                "gen-req",
                self.cert_name,
            ],
            cwd=self.conf.DATA_DIR,
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to generate csr")
            print(compl.stderr.decode())
        else:  # (Path(conf.PKI_DIR) / "ca.crt").exists():
            print(f"csr created")
            print(compl.stdout.decode())

    def ensure_sign_req(self):
        if not all(
            [
                self.conf.PKI_DIR.exists(),
                (self.conf.PKI_DIR / "ca.crt").exists(),
                (self.conf.PKI_DIR / "reqs" / f"{self.cert_name}.req").exists(),
            ]
        ):
            return

        if (self.conf.PKI_DIR / "issued" / f"{self.cert_name}.crt").exists():
            return

        print("Signing CSR")
        compl = subprocess.run(
            args=[
                str(self.conf.EASYRSA_BIN),
                "--batch",
                "--no-pass",
                "sign-req",
                "server",
                self.cert_name,
            ],
            cwd=self.conf.DATA_DIR,
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to sign csr")
            print(compl.stderr.decode())
        else:  # (Path(conf.PKI_DIR) / "ca.crt").exists():
            print(f"csr signed")
            print(compl.stdout.decode())


def register_device(context, device_class, client_conf, db):
    def device_factory():
        data = {
            "conf": client_conf,
            "db": db,
            "service_id": "device",
        }
        return device_class(**data)
    register_factory(
        context,
        device_class,
        device_factory,
        ping=lambda svc: svc.ping()
    )
