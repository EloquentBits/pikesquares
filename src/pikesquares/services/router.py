import json
from pathlib import Path

# import zmq
from tinydb import Query
import pydantic

from pikesquares import get_first_available_port
from pikesquares.services.base import BaseService
from ..presets.routers import HttpsRouterSection, HttpRouterSection

__all__ = (
    "HttpRouter",
    "HttpsRouter",
)


class HttpsRouter(BaseService):

    address: str

    # zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / "projects" / f"{self.service_id}.json"

    # @pydantic.computed_field
    # def socket_address(self) -> str:
    #    return f"127.0.0.1:{get_first_available_port(port=3017)}"

    # @pydantic.computed_field
    # def stats_address(self) -> str:
    # return f"127.0.0.1:{get_first_available_port(port=9897)}"

    @pydantic.computed_field
    def subscription_server_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=5600)}"

    # @pydantic.computed_field
    # def resubscribe_to(self) -> Path:
        # resubscribe_to: str = None,
    #    return Path()

    @pydantic.computed_field
    def port(self) -> str | None:
        try:
            return self.address.split(":")[-1]
        except IndexError:
            pass

    def up(self):
        self.prepare_service_config()
        self.save_config()
        self.write_config()

    def write_config(self):
        # if all([
        #    self.service_config,
        #    isinstance(self.service_config, Path),
        #    self.service_config.exists()]):
        #    msg = json.dumps(self.config_json).encode()
        #   self.service_config.read_text()

        #    print("sending https router config to zmq")
        #    self.zmq_socket.send_multipart(
        #        [
        #            b"touch",
        #            self.config_name.encode(),
        #            msg,
        #        ]
        #    )
        #    print("sent https router config to zmq")
        # else:
        #    print(f"DID NOT SEND https router config to zmq {str(self.service_config.resolve())}")

        self.service_config.parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

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

        config = HttpsRouterSection(self).\
                as_configuration().format(formatter="json")
        self.config_json = json.loads(config)
        #self.config_json["uwsgi"]["show-config"] = True
        #self.config_json["uwsgi"]["strict"] = True
        #self.config_json["uwsgi"]["notify-socket"] = str(self.notify_socket)

        # print(f"{wsgi_app_opts=}")
        # print(f"wsgi app {self.config_json=}")
        # empjs["uwsgi"]["plugin"] = "emperor_zeromq"
        # self.service_config.write_text(json.dumps(self.config_json))

    def connect(self):
        pass
        # print(f"Connecting to zmq emperor  {self.conf.EMPEROR_ZMQ_ADDRESS}")
        # self.zmq_socket.connect(f"tcp://{self.conf.EMPEROR_ZMQ_ADDRESS}")

    def start(self):
        pass

    def stop(self):
        pass
        # self.zmq_socket.send_multipart([
        #    b"destroy",
        #    self.config_name.encode(),
        # ])
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


class HttpRouter(BaseService):

    address: str
    is_internal: bool = False
    is_enabled: bool = True
    is_app: bool = False

    #zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    def up(self):
        self.prepare_service_config()
        self.save_config()
        self.write_config()

    def write_config(self):
        # if all([
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
        # else:
        #    print(f"DID NOT SEND https router config to zmq {str(self.service_config.resolve())}")

        self.service_config.parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

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

        section = HttpRouterSection(self)
        self.config_json = json.loads(
                section.as_configuration().format(formatter="json"))

        # self.config_json["uwsgi"]["show-config"] = True
        # self.config_json["uwsgi"]["strict"] = True
        # self.config_json["uwsgi"]["notify-socket"] = str(self.notify_socket)

        # print(f"{wsgi_app_opts=}")
        # print(f"wsgi app {self.config_json=}")
        # empjs["uwsgi"]["plugin"] = "emperor_zeromq"
        # self.service_config.write_text(json.dumps(self.config_json))

    def connect(self):
        pass
        #print(f"Connecting to zmq emperor  {self.conf.EMPEROR_ZMQ_ADDRESS}")
        #self.zmq_socket.connect(f"tcp://{self.conf.EMPEROR_ZMQ_ADDRESS}")

    def start(self):
        pass

    def stop(self):
        pass
        # self.zmq_socket.send_multipart([
        #    b"destroy",
        #    self.config_name.encode(),
        # ])
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
