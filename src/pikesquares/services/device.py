import json
import os
import sys
from pathlib import Path

from cuid import cuid
from tinydb import TinyDB, Query
#from uwsgiconf import uwsgi

from pikesquares import (
    get_first_available_port
)
from ..presets.device import DeviceSection
from ..conf import ClientConfig
from .project import project_up
from .router import https_router_up
from . import (
    Handler, 
    HandlerFactory, 
    Device, 
)


@HandlerFactory.register('Device')
class DeviceService(Handler):

    is_internal: bool = True
    is_enabled: bool = True
    is_app: bool = False

    config_json = {}

    def prepare_service_config(self):
        with TinyDB(self.svc_model.device_db_path) as db:
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

            devices_db = db.table('devices')
            devices_db.upsert(
                {
                    'service_type': self.handler_name, 
                    'service_config': self.config_json,
                },
                Query().service_type == self.handler_name,
            )
            print(f"DeviceService updated device_db")

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

        self.svc_model.service_config.write_text(
            json.dumps(self.config_json)
        )
        pyuwsgi.run([
            "--json",
            f"{str(self.svc_model.service_config.resolve())}"
        ])

    def stop(self):
        pass

        #res = device_config.main_process.actions.fifo_write(target, command)


def device_write_fifo(conf: ClientConfig, command: str, console) -> None:
    """
    Write command to master fifo named pipe
    """
    if not command in ["r", "q", "s"]:
        console.warning("unknown master fifo command '{command}'")
        return

    svc_model = Device(
        service_id="device", 
        conf=conf,
    )
    svc = HandlerFactory.make_handler("Device")(svc_model)
    svc.prepare_service_config()
    svc.write_fifo(command)


def device_up(conf: ClientConfig, console) -> None:

    svc_model = Device(
        service_id="device", 
        conf=conf,
    )
    svc = HandlerFactory.make_handler("Device")(svc_model)

    svc.prepare_service_config()

    with TinyDB(svc_model.device_db_path) as db:
        if not db.table('projects').all():
            for proj_config in (Path(conf.CONFIG_DIR) / "projects").glob("project_*.json"):
                for app_config in (Path(conf.CONFIG_DIR) / \
                        proj_config.stem / "apps").glob("*.json"):
                    console.info(f"found loose app config. deleting {app_config.name}")
                    app_config.unlink()
                console.info(f"found loose project config. deleting {proj_config.name}")
                proj_config.unlink()
            console.info("creating sandbox project.")
            project_up(conf, "sandbox", f"project_{cuid()}")

        if not db.table('routers').all():
            for router_config in (Path(conf.CONFIG_DIR) / "projects").glob("router_*.json"):
                console.info(f"found loose router config. deleting {router_config.name}")
                router_config.unlink()

            https_router_port = str(get_first_available_port(port=8443))
            console.info(f"no routers exist. creating one on port [{https_router_port}]")
            https_router_up(
                conf, 
                f"router_{cuid()}", 
                f"0.0.0.0:{https_router_port}",
            )
    svc.start()


