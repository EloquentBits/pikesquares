import uuid
from pathlib import Path

import pydantic
import structlog
from cuid import cuid
from sqlmodel import Field, Relationship, SQLModel

# from pikesquares import get_first_available_port
from pikesquares.conf import ensure_system_path
from pikesquares.presets.routers import HttpRouterSection, HttpsRouterSection

from .base import ServiceBase, TimeStampedBase
from .device import Device
from uwsgiconf.options.routing_routers import RouterTunTap

logger = structlog.getLogger()


class TuntapRouter(ServiceBase, table=True):
    """tuntap router"""

    __tablename__ = "tuntap_routers"

    name: str = Field(default="device0", max_length=32)
    socket: str | None = Field(max_length=150, default=None)
    ip: str | None = Field(max_length=25, default=None)
    netmask: str | None = Field(max_length=25, default=None)
    device_id: str | None = Field(default=None, foreign_key="devices.id")
    device: Device = Relationship(back_populates="tuntap_routers")

    tuntap_devices: list["TuntapDevice"] = Relationship(back_populates="tuntap_router")


class TuntapDevice(TimeStampedBase, table=True):
    """tuntap device"""

    __tablename__ = "tuntap_devices"


    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4()),
        max_length=36,
    )
    name: str = Field(default="device0", max_length=32)
    ip: str | None = Field(max_length=25, default=None)
    netmask: str | None = Field(max_length=25, default=None)

    tuntap_router_id: int | None = Field(foreign_key="tuntap_routers.id", unique=True)
    tuntap_router: TuntapRouter | None = Relationship(back_populates="tuntap_devices")



class HttpRouter(ServiceBase, table=True):

    __tablename__ = "http_routers"

    name: str = Field(default="http-router0", max_length=32)

    address: str | None = Field(default=None, max_length=100)
    subscription_server_address: str | None = Field(default=None, max_length=100)

    device_id: str | None = Field(default=None, foreign_key="devices.id")
    device: Device = Relationship(back_populates="routers")

    @property
    def uwsgi_config_section_class(self) -> HttpRouterSection | HttpsRouterSection:
        if int(self.port) >= 8443:
            return HttpsRouterSection
        return HttpRouterSection


    def get_uwsgi_config(self):
        section = self.uwsgi_config_section_class(self)
        
        """
        ; we need it as the vassal have no way to know it is jailed
        ; without it post_jail plugin hook would be never executed
        jailed = true
        ; create uwsgi0 tun interface and force it to connect to the Emperor exposed unix socket
        tuntap-device = uwsgi0 ../run/tuntap.socket
        """

        #tuntap_router_socket_address
        if 0:
            section._set("jailed", "true")

            # http_router_cma30m5zj0002ljj1hh1hqsm4
            network_device_name = f"psq-router-{self.service_id.split('_')[-1][:5]}"

            router = RouterTunTap().device_connect(
                device_name=network_device_name,
                socket="/tmp/tuntap.socket",
            ).device_add_rule(
                direction="in",
                action="route",
                src="192.168.0.1",
                dst="192.168.0.2",
                target="10.20.30.40:5060",
            )
            section.routing.use_router(router)

            #; bring up loopback
            #exec-as-root = ifconfig lo up
            section.main_process.run_command_on_event(
                command="ifconfig lo up",
                phase=section.main_process.phases.PRIV_DROP_PRE,
            )
            # bring up interface uwsgi0
            #exec-as-root = ifconfig uwsgi0 192.168.0.2 netmask 255.255.255.0 up
            section.main_process.run_command_on_event(
                command=f"ifconfig {network_device_name} 192.168.0.1 netmask 255.255.255.0 up",
                phase=section.main_process.phases.PRIV_DROP_PRE,
            )
            # and set the default gateway
            #exec-as-root = route add default gw 192.168.0.1
            section.main_process.run_command_on_event(
                command="route add default gw 192.168.0.1",
                phase=section.main_process.phases.PRIV_DROP_PRE,
            )

            section.main_process.run_command_on_event(
                command="",
                phase=section.main_process.phases.PRIV_DROP_PRE,
            )
            # ping something to register
            #exec-as-root = ping -c 1 192.168.0.1



        return super().get_uwsgi_config(zmq_monitor=zmq_monitor, tuntap_router=tuntap_router)

    @property
    def service_config(self) -> Path | None:
        if self.enable_dir_monitor:
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

    @pydantic.computed_field
    @property
    def enable_dir_monitor(self) -> bool:
        return False  # self.device.enable_dir_monitor

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
