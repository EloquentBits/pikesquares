from pathlib import Path

import pydantic
import structlog
from cuid import cuid
from sqlmodel import Field, Relationship

# from pikesquares import get_first_available_port
from pikesquares.conf import ensure_system_path
from pikesquares.presets.routers import HttpRouterSection, HttpsRouterSection

from .base import ServiceBase
from .device import Device

logger = structlog.getLogger()


class BaseRouter(ServiceBase, table=True):

    name: str = Field(default="HTTP Router", max_length=32)

    address: str | None = Field(default=None, max_length=100)
    subscription_server_address: str | None = Field(default=None, max_length=100)

    device_id: str | None = Field(default=None, foreign_key="device.id")
    device: Device = Relationship(back_populates="routers")

    @property
    def uwsgi_config_section_class(self) -> HttpRouterSection | HttpsRouterSection:
        if int(self.port) >= 8443:
            return HttpsRouterSection
        return HttpRouterSection

    @pydantic.computed_field
    @property
    def service_config(self) -> Path | None:
        if self.device.enable_dir_monitor:
            service_config_dir = ensure_system_path(Path(self.config_dir) / "projects")
            return service_config_dir / f"{self.service_id}.ini"

    # @pydantic.computed_field
    # def resubscribe_to(self) -> Path:
    # resubscribe_to: str = None,
    #    return Path()

    @pydantic.computed_field
    @property
    def port(self) -> str | None:
        if self.address:
            try:
                return self.address.split(":")[-1]
            except IndexError:
                pass

    """
    https_router = await uow.routers.get_by_name("default-https-router")
    if not https_router:
        https_router = BaseRouter(
            service_id=f"https_router_{cuid()}",
            name="default-https-router",
            address=f"0.0.0.0:{str(get_first_available_port(port=8443))}",
            subscription_server_address=f"127.0.0.1:{get_first_available_port(port=5600)}",
            **create_kwargs,
        )
        await uow.routers.add(https_router)
        await uow.commit()
        logger.debug(f"Created {https_router=}")
    else:
        logger.debug(f"Using existing http router {https_router=}")

    context["https_router"] = https_router
    """


"""
class HttpsRouter(BaseRouter):

    # config_section_class: Section = HttpsRouterSection

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
        logger.debug("== HttpsRouter.ping ==")
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
            self.service_config = Path(self.config_dir) /  "routers" / f"{self.service_id}.json"
        if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))


class HttpRouter(BaseRouter):

    # zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    # config_section_class: Section = HttpRouterSection

    def ping(self) -> None:
        logger.debug("== HttpRouter.ping ==")

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
            self.service_config = Path(self.config_dir) /  "routers" / f"{self.service_id}.json"
        if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))

DefaultHttpsRouter = NewType("DefaultHttpsRouter", HttpsRouter)
DefaultHttpRouter = NewType("DefaultHttpRouter", HttpRouter)


def register_router(
        context: dict,
        address: str,
        subscription_server_address: str,
        plugins: list,
        router_type: DefaultHttpsRouter | DefaultHttpRouter,
        router_class: HttpsRouter | HttpRouter,
        conf: AppConfig,
        db: TinyDB,
        build_config_on_init: bool | None,
    ) -> None:

    def default_router_factory():
        router_alias = "https" if "https" in router_class.__name__.lower() else "http"
        kwargs = {
            "address": address,
            "subscription_server_address": subscription_server_address,
            "conf": conf,
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

"""
