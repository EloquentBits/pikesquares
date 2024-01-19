import json
import os
import sys
from pathlib import Path
from typing import Protocol, TypeVar

#import zmq
from tinydb import TinyDB, Query
#from uwsgiconf import uwsgi

from ..presets.device import DeviceSection
from ..conf import ClientConfig
from . import (
    Handler, 
    HandlerFactory, 
    Device, 
)


@HandlerFactory.register('Device')
class DeviceService(Handler):

    is_internal = True
    is_enabled = True

    def prepare_service_config(self):
        # TODO  self.service_config.tofile()

        with TinyDB(self.svc_model.device_db_path) as db:
            config = json.loads(
                DeviceSection(
                    self.svc_model,
                ).as_configuration().format(formatter="json")
            )
            config["uwsgi"]["show-config"] = True
            #empjs["uwsgi"]["emperor"] = f"zmq://tcp://{self.client_config.EMPEROR_ZMQ_ADDRESS}"
            # empjs["uwsgi"]["emperor"] = f"{self.client_config.CONFIG_DIR}/project_clo7af2mb0000nldcne2ssmrv/apps"
            #config["uwsgi"]["plugin"] = "emperor_zeromq"

            #routers_dir = Path(self.svc_model.client_config.CONFIG_DIR) / "routers"
            #routers_dir.mkdir(parents=True, exist_ok=True)
            #config["uwsgi"]["emperor"] = str(routers_dir.resolve())

            config["uwsgi"]["emperor-wrapper"] = str((Path(self.svc_model.client_config.VENV_DIR) / "bin/uwsgi").resolve())

            self.svc_model.service_config.write_text(
                json.dumps(config)
            )

            devices_db = db.table('devices')
            devices_db.upsert(
                {
                    'service_type': self.handler_name, 
                    'service_config': config,
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
    svc.start()


