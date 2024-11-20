import json
# from pathlib import Path

# import zmq
from tinydb import Query

from pikesquares.services import BaseService
from ..presets.routers import HttpsRouterSection, HttpRouterSection

__all__ = (
    "HttpRouterService",
    "HttpsRouterService",
)


class HttpsRouterService(BaseService):

    address: str

    # zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    def up(self, address: str):
        self.address = address
        self.prepare_service_config()
        self.save_config()
        self.start()

    def save_config(self):
        routers_db = self.db.table("routers")
        routers_db.upsert(
            {
                "service_type": self.handler_name,
                "service_id": self.service_id,
                "address": self.address,
                "service_config": self.config_json,
            },
            Query().service_id == self.service_id,
        )

    def prepare_service_config(self) -> None:

        def https_router_provision_cert():
            pass

        https_router_provision_cert()
    
        section = HttpsRouterSection(self.self, self.address)
        self.config_json = json.loads(
                section.as_configuration().format(formatter="json"))
        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["strict"] = True
        self.config_json["uwsgi"]["notify-socket"] = str(self.notify_socket)

        # print(f"{wsgi_app_opts=}")
        # print(f"wsgi app {self.config_json=}")
        #empjs["uwsgi"]["plugin"] = "emperor_zeromq"
        #self.service_config.write_text(json.dumps(self.config_json))

    def connect(self):
        pass
        #print(f"Connecting to zmq emperor  {self.conf.EMPEROR_ZMQ_ADDRESS}")
        #self.zmq_socket.connect(f"tcp://{self.conf.EMPEROR_ZMQ_ADDRESS}")

    def start(self):
        #if all([
        #    self.service_config, 
        #    isinstance(self.service_config, Path), 
        #    self.service_config.exists()]):
        #    msg = json.dumps(self.config_json).encode()
            #self.service_config.read_text()

        #    print("sending https router config to zmq")
        #    self.zmq_socket.send_multipart(
        #        [
        #            b"touch", 
        #            self.config_name.encode(), 
        #            msg,
        #        ]
        #    )
        #    print("sent https router config to zmq")
        #else:
        #    print(f"DID NOT SEND https router config to zmq {str(self.service_config.resolve())}")

        self.service_config.parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

    def stop(self):
        pass
        #self.zmq_socket.send_multipart([
        #    b"destroy",
        #    self.config_name.encode(),
        #])
    """
    def connect(self):
        pass
        #emperor_zmq_opt = uwsgi.opt.get('emperor', b'').decode()
        #zmq_port = emperor_zmq_opt.split(":")[-1]
        #zmq_port = "5500"
        #self.zmq_socket.connect(f'tcp://127.0.0.1:{zmq_port}')

    def start(self):
        if not self.is_started() and str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(
                str(self.service_config),
                self.service_config.removesuffix(".stopped")
            )

        Path(self.service_config).parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

    def stop(self):
        if self.service_config is None:
            self.service_config = Path(self.conf.CONFIG_DIR) /  "routers" / f"{self.service_id}.json"
        if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))
    """


class HttpRouterService(BaseService):

    address: str
    is_internal: bool = False
    is_enabled: bool = True
    is_app: bool = False

    config_json = {}
    #zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    def up(self, address:str):
        self.address = address
        self.prepare_service_config()
        self.save_config()
        self.start()

    def save_config(self):
        routers_db = self.db.table('routers')
        routers_db.upsert(
            {
                'service_type': self.handler_name, 
                'service_id': self.service_id,
                'address': self.address,
                'service_config': self.config_json,
            },
            Query().service_id == self.service_id,
        )

    def prepare_service_config(self) -> None:

        section = HttpRouterSection(self.self, self.address)
        self.config_json = json.loads(
                section.as_configuration().format(formatter="json"))
        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["strict"] = True
        self.config_json["uwsgi"]["notify-socket"] = str(self.notify_socket)

        # print(f"{wsgi_app_opts=}")
        # print(f"wsgi app {self.config_json=}")
        #empjs["uwsgi"]["plugin"] = "emperor_zeromq"
        #self.service_config.write_text(json.dumps(self.config_json))

    def connect(self):
        pass
        #print(f"Connecting to zmq emperor  {self.conf.EMPEROR_ZMQ_ADDRESS}")
        #self.zmq_socket.connect(f"tcp://{self.conf.EMPEROR_ZMQ_ADDRESS}")

    def start(self):
        #if all([
        #    self.service_config, 
        #    isinstance(self.service_config, Path), 
        #    self.service_config.exists()]):
        #    msg = json.dumps(self.config_json).encode()
            #self.service_config.read_text()

        #    print("sending https router config to zmq")
        #    self.zmq_socket.send_multipart(
        #        [
        #            b"touch", 
        #            self.config_name.encode(), 
        #            msg,
        #        ]
        #    )
        #    print("sent https router config to zmq")
        #else:
        #    print(f"DID NOT SEND https router config to zmq {str(self.service_config.resolve())}")

        self.service_config.parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

    def stop(self):
        pass
        #self.zmq_socket.send_multipart([
        #    b"destroy",
        #    self.config_name.encode(),
        #])
    """
    def connect(self):
        pass
        #emperor_zmq_opt = uwsgi.opt.get('emperor', b'').decode()
        #zmq_port = emperor_zmq_opt.split(":")[-1]
        #zmq_port = "5500"
        #self.zmq_socket.connect(f'tcp://127.0.0.1:{zmq_port}')

    def start(self):
        if not self.is_started() and str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(
                str(self.service_config),
                self.service_config.removesuffix(".stopped")
            )

        Path(self.service_config).parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

    def stop(self):
        if self.service_config is None:
            self.service_config = Path(self.conf.CONFIG_DIR) /  "routers" / f"{self.service_id}.json"
        if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))
    """
