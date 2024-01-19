import json
import os
import sys
from pathlib import Path
from typing import Protocol, TypeVar

from cuid import cuid
import randomname

#import zmq
from tinydb import TinyDB, Query
#from uwsgiconf import uwsgi

from ..presets.device import DeviceSection
from ..conf import ClientConfig
from .project import project_up
from . import (
    Handler, 
    HandlerFactory, 
    Device, 
)


@HandlerFactory.register('Device')
class DeviceService(Handler):

    is_internal = True
    is_enabled = True

    config_json = {}

    def prepare_service_config(self):
        # TODO  self.service_config.tofile()

        with TinyDB(self.svc_model.device_db_path) as db:
            self.config_json = json.loads(
                DeviceSection(
                    self.svc_model,
                ).as_configuration().format(formatter="json")
            )
            self.config_json["uwsgi"]["show-config"] = True
            #empjs["uwsgi"]["emperor"] = f"zmq://tcp://{self.client_config.EMPEROR_ZMQ_ADDRESS}"
            # empjs["uwsgi"]["emperor"] = f"{self.client_config.CONFIG_DIR}/project_clo7af2mb0000nldcne2ssmrv/apps"
            #config["uwsgi"]["plugin"] = "emperor_zeromq"

            #routers_dir = Path(self.svc_model.client_config.CONFIG_DIR) / "routers"
            #routers_dir.mkdir(parents=True, exist_ok=True)
            #config["uwsgi"]["emperor"] = str(routers_dir.resolve())

            self.config_json["uwsgi"]["emperor-wrapper"] = str((Path(self.svc_model.client_config.VENV_DIR) / "bin/uwsgi").resolve())
            #self.config_json["uwsgi"]["spooler-import"] = "pikesquares.tasks.ensure_up"

            devices_db = db.table('devices')
            devices_db.upsert(
                {
                    'service_type': self.handler_name, 
                    'service_config': self.config_json,
                },
                Query().service_type == self.handler_name,
            )

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


def device_up(client_config: ClientConfig) -> None:

    svc_model = Device(
        service_id="device", 
        client_config=client_config,
    )
    svc = HandlerFactory.make_handler("Device")(svc_model)
    svc.prepare_service_config()

    with TinyDB(svc_model.device_db_path) as db:
        projects_db = db.table('projects')
        if not projects_db.all():
            print("no projects exist. creating one.")
            project_up(
                client_config, 
                randomname.get_name(), 
                f"project_{cuid()}"
            )

    svc.start()


