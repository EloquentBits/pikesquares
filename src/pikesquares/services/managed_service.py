import json
from pathlib import Path

#import zmq
from tinydb import TinyDB, Query

#from ..presets.routers import HttpsRouterSection, HttpRouterSection
from ..presets import ManagedServiceSection
from . import (
    Handler, 
    HandlerFactory, 
)

__all__ = (
    "ManagedDaemonService",
)


@HandlerFactory.register('Managed-Daemon')
class ManagedDaemonService(Handler):

    is_internal: bool = False
    is_enabled: bool = True
    is_app: bool = False

    config_json = {}
    #zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    def up(self, command: str):
        self.command = command
        self.prepare_service_config()
        self.save_config()
        self.start()

    def save_config(self):
        with TinyDB(self.svc_model.device_db_path) as db:
            routers_db = db.table('managed-services')
            routers_db.upsert(
                {
                    'service_type': self.handler_name, 
                    'service_id': self.svc_model.service_id,
                    'command': self.command,
                    'service_config': self.config_json,
                },
                Query().service_id == self.svc_model.service_id,
            )

    def prepare_service_config(
            self,
            ) -> None:

        section = ManagedServiceSection(
                self.svc_model, 
                self.command
        )
        self.config_json = json.loads(
                section.as_configuration().format(formatter="json"))
        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["strict"] = True

    def connect(self):
        pass

    def start(self):
        self.svc_model.service_config.parent.mkdir(
                parents=True, exist_ok=True
        )
        self.svc_model.service_config.write_text(
                json.dumps(self.config_json)
        )

    def stop(self):
        pass
