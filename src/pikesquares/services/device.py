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
from . import Handler, HandlerFactory


@HandlerFactory.register('Device')
class DeviceService(Handler):

    is_internal = True
    is_enabled = True

    def prepare_service_config(self):
        # TODO  self.service_config.tofile()

        self.service_config = Path(self.client_config.CONFIG_DIR) / "device.json"
        with TinyDB(self.device_db_path) as db:
            config = json.loads(
                DeviceSection(
                    self.client_config,
                    self.service_id,
                ).as_configuration().format(formatter="json")
            )
            config["uwsgi"]["show-config"] = True
            #empjs["uwsgi"]["emperor"] = f"zmq://tcp://{self.client_config.EMPEROR_ZMQ_ADDRESS}"
            # empjs["uwsgi"]["emperor"] = f"{self.client_config.CONFIG_DIR}/project_clo7af2mb0000nldcne2ssmrv/apps"
            #config["uwsgi"]["plugin"] = "emperor_zeromq"
            config["uwsgi"]["emperor-wrapper"] = str((Path(self.client_config.VENV_DIR) / "bin/uwsgi").resolve())

            routers_dir = Path(self.client_config.CONFIG_DIR) / "routers"
            routers_dir.mkdir(parents=True, exist_ok=True)
            #empjs["uwsgi"]["emperor"] = str(routers_dir.resolve())

            self.service_config.write_text(
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
            f"{str(self.service_config.resolve())}"
        ])

    def stop(self):
        pass


def device_up(client_config: ClientConfig) -> None:
    device = HandlerFactory.make_handler("Device")(
        service_id="device", 
        client_config=client_config,
    )
    device.prepare_service_config()
    device.start()


