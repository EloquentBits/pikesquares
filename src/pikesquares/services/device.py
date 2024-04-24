import shutil
import json
import os
import sys
from pathlib import Path
import subprocess

from cuid import cuid
from tinydb import TinyDB, Query
#from uwsgiconf import uwsgi

from ..presets.device import DeviceSection
from . import Handler, HandlerFactory
from pikesquares.cli.console import console

__all__ = ("DeviceService",)


@HandlerFactory.register('Device')
class DeviceService(Handler):

    is_internal: bool = True
    is_enabled: bool = True
    is_app: bool = False

    config_json = {}

    def up(self):
        from pikesquares.services import (
            Project, 
            HttpsRouter,
            HttpRouter,
        )
        #conf.DAEMONIZE = not foreground
        #self.setup_pki()

        self.prepare_service_config()
        self.save_config()
        self.write_config()

        self.sync_db_with_filesystem()

        with TinyDB(self.svc_model.device_db_path) as db:
            for project_doc in db.table('projects'):
                project_handler = HandlerFactory.make_handler("Project")(
                    Project(service_id=project_doc.get("service_id"))
                )
                project_handler.up(project_doc.get("name"))

            for router_doc in db.table('routers'):
                handler_name = None
                handler_class = None
                if router_doc.get("service_type") == "HttpRouterService":
                    handler_name = "Http-Router"
                    handler_class = HttpRouter
                elif router_doc.get("service_type") == "HttpRouterService":
                    handler_name = "Https-Router"
                    handler_class = HttpsRouter

                if all([
                    handler_name,  
                    handler_name == "Http-Router", 
                    handler_class]):
                    HandlerFactory.make_handler(handler_name)(
                            handler_class(service_id=router_doc.get("service_id")
                    )).up(router_doc.get("address").split("://")[-1])

        self.start()

    def save_config(self):
        with TinyDB(self.svc_model.device_db_path) as db:
            devices_db = db.table('devices')
            devices_db.upsert(
                {
                    'service_type': self.handler_name, 
                    'service_config': self.config_json,
                },
                Query().service_type == self.handler_name,
            )

    def write_config(self):
        self.svc_model.service_config.write_text(
            json.dumps(self.config_json)
        )

    def prepare_service_config(self):
        self.config_json = json.loads(
            DeviceSection(
                self.svc_model,
            ).as_configuration().format(formatter="json")
        )
        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["emperor-wrapper"] = \
            str((Path(self.svc_model.conf.VIRTUAL_ENV) / "bin/uwsgi").resolve())

            #empjs["uwsgi"]["emperor"] = f"zmq://tcp://{self.conf.EMPEROR_ZMQ_ADDRESS}"
            #config["uwsgi"]["plugin"] = "emperor_zeromq"
            #self.config_json["uwsgi"]["spooler-import"] = "pikesquares.tasks.ensure_up"
    def connect(self):
        pass

    def start(self):

        # we import `pyuwsgi` with `dlopen` flags set to `os.RTLD_GLOBAL` such that
        # uwsgi plugins can discover uwsgi's globals (notably `extern ... uwsgi`)
        if hasattr(sys, 'setdlopenflags'):
            orig = sys.getdlopenflags()
            try:
                sys.setdlopenflags(orig | os.RTLD_GLOBAL)
                import pyuwsgi
            finally:
                sys.setdlopenflags(orig)
        else:  # ah well, can't control how dlopen works here
            import pyuwsgi

        console.info("starting PikeSquares Server")
        pyuwsgi.run([
            "--json",
            f"{str(self.svc_model.service_config.resolve())}"
        ])

    def stop(self):
        if self.svc_model.get_service_status() == "running":
            self.write_master_fifo("q")

        #res = device_config.main_process.actions.fifo_write(target, command)

    def sync_db_with_filesystem(self):
        with TinyDB(self.svc_model.device_db_path) as db:
            if not db.table('projects').all():
                for proj_config in (self.svc_model.config_dir / "projects").glob("project_*.json"):
                    for app_config in (self.svc_model.config_dir / \
                            proj_config.stem / "apps").glob("*.json"):
                        console.info(f"found loose app config. deleting {app_config.name}")
                        app_config.unlink()
                    console.info(f"found loose project config. deleting {proj_config.name}")
                    proj_config.unlink()
                #console.info("creating sandbox project.")
                #project_up(conf, "sandbox", f"project_{cuid()}")

            if not db.table('routers').all():
                for router_config in (self.svc_model.config_dir / "projects").glob("router_*.json"):
                    console.info(f"found loose router config. deleting {router_config.name}")
                    router_config.unlink()

    def drop_db_tables(self):
        with TinyDB(self.svc_model.data_dir / "device-db.json") as db:
            db.drop_table('projects')
            db.drop_table('routers')
            db.drop_table('apps')

    def delete_configs(self):
        for proj_config in (self.svc_model.config_dir / "projects").glob("project_*.json"):
            for app_config in (self.svc_model.config_dir / \
                    proj_config.stem / "apps").glob("*.json"):
                console.info(f"deleting {app_config.name}")
                app_config.unlink()

                # FIXME
                #app_log = self.svc_model.log_dir / app_config.stem / ".log"
                #app_log.unlink(missing_ok=True)
                #console.info(f"deleting {app_log.name}")

            console.info(f"deleting {proj_config.name}")
            proj_config.unlink()

        for router_config in (self.svc_model.config_dir / "projects").glob("router_*.json"):
            console.info(f"found router config. deleting {router_config.name}")
            router_config.unlink()

    #def delete_logs(self):
    #    for logfile in self.svc_model.log_dir.glob("*.log"):

    def uninstall(self, dry_run=False):
        for user_dir in [
                self.svc_model.data_dir, 
                self.svc_model.config_dir, 
                self.svc_model.run_dir, 
                self.svc_model.log_dir,
                self.svc_model.plugins_dir,
                self.svc_model.pki_dir]:
            if not dry_run:
                try:
                    shutil.rmtree(str(user_dir))
                    console.info(f"deleted {str(user_dir)}")
                except FileNotFoundError:
                    pass

    def setup_pki(self):
        if all([
            self.ensure_pki(),
            self.ensure_build_ca(),
            self.ensure_csr(),
            self.ensure_sign_req(),]):
            console.success(f"Wildcard certificate created.")

    def ensure_pki(self):
        if self.svc_model.pki_dir.exists():
            return

        compl = subprocess.run(
            args=[
                str(self.svc_model.easyrsa),
                "init-pki",
            ],
            cwd=str(self.svc_model.data_dir),
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to initialize PKI")
        else:
            print(f"Initialized PKI @ {self.svc_model.pki_dir}")
        #set(compl.stdout.decode().split("\n"))

    def ensure_build_ca(self):
        if not self.svc_model.pki_dir.exists():
            print(f"Unable to create CA. PKI was not located.")
            return

        if (self.svc_model.pki_dir / "ca.crt").exists():
            return

        print("building CA")

        compl = subprocess.run(
            args=[
                str(self.svc_model.easyrsa),
                '--req-cn=PikeSquares Proxy',
                "--batch",
                "--no-pass",
                "build-ca",
            ],
            cwd=self.svc_model.data_dir,
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to build CA")
            print(compl.stderr.decode())
        elif (self.svc_model.pki_dir / "ca.crt").exists(): 
            print(f"CA cert created")
            print(compl.stdout.decode())

        #set(compl.stdout.decode().split("\n"))

    def ensure_csr(self):
        if not self.svc_model.pki_dir.exists():
            print("Unable to create a CSR. PKI was not located.")
            return

        if not (self.svc_model.pki_dir / "ca.crt").exists():
            print("Unable to create a CSR. CA was not located.")
            return

        if (self.svc_model.pki_dir / "reqs" / f"{self.svc_model.cert_name}.req").exists():
            return

        print("generating CSR")
        compl = subprocess.run(
            args=[
                str(self.svc_model.easyrsa),
                "--batch",
                "--no-pass",
                "--silent",
                "--subject-alt-name=DNS:*.pikesquares.dev",
                "gen-req",
                self.svc_model.cert_name,
            ],
            cwd=self.svc_model.data_dir,
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to generate csr")
            print(compl.stderr.decode())
        else: # (Path(conf.PKI_DIR) / "ca.crt").exists(): 
            print(f"csr created")
            print(compl.stdout.decode())

    def ensure_sign_req(self):
        if not all([self.svc_model.pki_dir.exists(),
                    (self.svc_model.pki_dir / "ca.crt").exists(),
                    (self.svc_model.pki_dir / "reqs" / f"{self.svc_model.cert_name}.req").exists()]):
            return

        if (self.svc_model.pki_dir / "issued" / f"{self.svc_model.cert_name}.crt").exists():
            return

        print("Signing CSR")
        compl = subprocess.run(
            args=[
                str(self.svc_model.easyrsa),
                "--batch",
                "--no-pass",
                "sign-req",
                "server",
                self.svc_model.cert_name,
            ],
            cwd=self.svc_model.data_dir,
            capture_output=True,
            check=True,
        )
        if compl.returncode != 0:
            print(f"unable to sign csr")
            print(compl.stderr.decode())
        else: # (Path(conf.PKI_DIR) / "ca.crt").exists(): 
            print(f"csr signed")
            print(compl.stdout.decode())



