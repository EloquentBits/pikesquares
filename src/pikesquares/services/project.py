import json
#import shutil
from pathlib import Path

#import zmq
from tinydb import TinyDB, Query
#from uwsgiconf import uwsgi

from ..presets.project import ProjectSection
from ..conf import ClientConfig
from . import (
    Handler, 
    HandlerFactory,
    Project,
)


@HandlerFactory.register('Project')
class ProjectService(Handler):

    name: str
    is_internal: bool = True
    is_enabled: bool = True
    is_app: bool = False

    #zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)
    config_json = {}

    def prepare_service_config(self, name: str):
        self.name = name

        with TinyDB(self.svc_model.device_db_path) as db:
            empjs = json.loads(ProjectSection(
                    self.svc_model
                ).as_configuration().format(formatter="json"))

            self.svc_model.service_config.write_text(json.dumps(empjs))
            self.config_json = json.loads(self.svc_model.service_config.read_text())

            #stats_addr = self.config_json["uwsgi"]["emperor-stats-server"]
            #self.config_json["uwsgi"]["emperor"] = zmq_addr #uwsgi.cache_get(zmq_addr_key, self.cache).decode()
            #self.config_json["uwsgi"]["emperor"] = self.svc_model.apps_dir

            #uwsgi.cache_update(f"{self.svc_model.service_id}-stats-addr", str(stats_addr), 0, self.svc_model.cache)

            self.config_json["uwsgi"]["emperor-wrapper"] = \
                str((Path(self.svc_model.conf.VIRTUAL_ENV) / "bin/uwsgi").resolve())

            self.config_json["uwsgi"]["show-config"] = True
            self.config_json["uwsgi"]["strict"] = True
            # self.config_json["uwsgi"]["plugin"] = "logfile"

            #if "logfile" in config_json["uwsgi"].get("plugin", ""):
            #    config_json["uwsgi"].pop("plugin")

            #self.svc_model.service_config.write_text(json.dumps(self.config_json))

            print("Updating projects db.")
            projects_db = db.table('projects')
            projects_db.upsert(
                {
                    'service_type': self.handler_name, 
                    'service_id': self.svc_model.service_id,
                    'service_config': self.config_json,
                    'name': self.name,
                },
                Query().service_id == self.svc_model.service_id,
            )
            print("Done updating projects db.")
    
    def connect(self):
        pass
        #print(f"Connecting to zmq emperor  {self.svc_model.conf.EMPEROR_ZMQ_ADDRESS}")
        #self.zmq_socket.connect(f"tcp://{self.svc_model.conf.EMPEROR_ZMQ_ADDRESS}")

    def start(self):
        #print("sending msg to zmq")
        #self.zmq_socket.send_multipart(
        #    [
        #        b"touch", 
        #        f"{self.svc_model.service_id}.json".encode(), 
        #        json.dumps(self.config_json).encode(),
        #    ]
        #)
        #print("sent msg to zmq")

        #if not self.is_started() and str(self.service_config.resolve()).endswith(".stopped"):
        #    shutil.move(
        #        str(self.service_config),
        #        self.service_config.removesuffix(".stopped")
        #    )

        self.svc_model.service_config.parent.mkdir(parents=True, exist_ok=True)
        self.svc_model.service_config.write_text(json.dumps(self.config_json))

    def stop(self):
        pass
        #self.zmq_socket.send_multipart([
        #    b"destroy",
        #    f"{self.svc_model.service_id}.json".encode(), 
        #])
        #if self.svc_model.service_config is None:
        #    self.svc_model.service_config = Path(self.conf.CONFIG_DIR) / \
        #            f"{self.svc_model.parent_service_id}" / "apps" \
        #            / f"{self.svc_model.service_id}.json"

        #if self.is_started() and not str(self.svc_model.service_config.resolve()).endswith(".stopped"):
        #    shutil.move(self.svc_model.service_config, self.svc_model.service_config.with_suffix(".stopped"))

def project_up(
        conf: ClientConfig, 
        name: str, 
        service_id:str) -> None:

    print(f'Starting {service_id}')

    svc_model = Project(
        service_id=service_id,
        conf=conf,
    )
    svc = HandlerFactory.make_handler("Project")(svc_model)
    svc.prepare_service_config(name)
    svc.connect()
    svc.start()

def projects_all(conf: ClientConfig):
    with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
        projects_db = db.table('projects')
        return projects_db.all()

def get_project(conf: ClientConfig, project_id):
    with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
        return db.table('projects').\
            get(Query().service_id == project_id)



