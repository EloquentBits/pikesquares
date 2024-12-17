import json
from pathlib import Path
from typing import NewType

# import zmq
from tinydb import Query, TinyDB
import pydantic

from pikesquares import conf, get_first_available_port
from pikesquares.presets import Section
from pikesquares.services.base import BaseService
from pikesquares.services import register_factory
from ..presets.routers import HttpsRouterSection, HttpRouterSection

__all__ = (
    "HttpRouter",
    "HttpsRouter",
)


class BaseRouter(BaseService):

    address: str
    subscription_server_address: str
    tiny_db_table: str = "routers"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / "projects" / f"{self.service_id}.json"

    @pydantic.computed_field
    def touch_reload_file(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / "projects" / f"{self.service_id}.json"

    def zmq_connect(self):
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

    def zmq_write_config(self):
        pass
        # if all([
        #    self.service_config,
        #    isinstance(self.service_config, Path),
        #    self.service_config.exists()]):
        #    msg = json.dumps(self.config_json).encode()
        # self.service_config.read_text()

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

    def save_config_to_tinydb(self, extra_data: dict = {}) -> None:
        super().save_config_to_tinydb(
            extra_data={"address": self.address}
        )

    @pydantic.computed_field
    def default_config_json(self) -> dict:
        section = self.config_section_class(self, self.plugins)
        config_json = json.loads(
                section.as_configuration().format(
                    formatter="json",
                    do_print=True,
                )
        )
        # self.config_json["uwsgi"]["show-config"] = True
        # self.config_json["uwsgi"]["strict"] = True
        # self.config_json["uwsgi"]["notify-socket"] = str(self.notify_socket)

        # print(f"{wsgi_app_opts=}")
        # print(f"wsgi app {self.config_json=}")
        # empjs["uwsgi"]["plugin"] = "emperor_zeromq"
        # self.service_config.write_text(json.dumps(self.config_json))
        return config_json

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


class HttpsRouter(BaseRouter):

    config_section_class: Section = HttpsRouterSection

    # zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    # {
    #        "version":"2.0.28",
    #        "pid":612604,
    #        "uid":1000,
    #        "gid":1000,
    #        "cwd":"/home/pk/.config/pikesquares/projects",
    #        "active_sessions":0,
    #        "http":[
    # "0.0.0.0:8444",
    # "127.0.0.1:5600"
    #        ],
    #        "subscriptions":[
    #        ],
    #        "cheap":0
    # }

    def ping(self) -> None:
        print("== HttpsRouter.ping ==")
        # if not is_port_open(self.api_port):
        #    raise PCAPIUnavailableError()

    # @pydantic.computed_field
    # def socket_address(self) -> str:
    #    return f"127.0.0.1:{get_first_available_port(port=3017)}"

    # @pydantic.computed_field
    # def stats_address(self) -> str:
    # return f"127.0.0.1:{get_first_available_port(port=9897)}"

    def https_router_provision_cert(self):
        pass

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


class HttpRouter(BaseRouter):

    # zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    config_section_class: Section = HttpRouterSection

    def ping(self) -> None:
        print("== HttpRouter.ping ==")

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


DefaultHttpsRouter = NewType("DefaultHttpsRouter", HttpsRouter)
DefaultHttpRouter = NewType("DefaultHttpRouter", HttpRouter)


def register_router(
        context: dict,
        address: str,
        subscription_server_address: str,
        plugins: list,
        router_type: DefaultHttpsRouter | DefaultHttpRouter,
        router_class: HttpsRouter | HttpRouter,
        client_conf: conf.ClientConfig,
        db: TinyDB,
        build_config_on_init: bool | None,
    ) -> None:

    def default_router_factory():
        router_alias = "https" if "https" in router_class.__name__.lower() else "http"
        kwargs = {
            "address": address,
            "subscription_server_address": subscription_server_address,
            "conf": client_conf,
            "db": db,
            "plugins": plugins,
            "service_id": f"default_{router_alias}_router",
            "build_config_on_init": build_config_on_init,
        }
        return router_class(**kwargs)

    register_factory(
        context,
        router_type,
        default_router_factory,
        ping=lambda svc: svc.ping(),
    )
