import logging
from typing import (
    Protocol,
    List,
    Tuple,
    overload,
)

from abc import abstractmethod
from collections.abc import Callable
from pathlib import Path

import pydantic
from pydantic.config import ConfigDict
from uwsgiconf import uwsgi
from tinydb import TinyDB

# from questionary import Style as QuestionaryStyle

from .. import get_first_available_port

# from ..cli.pki import CERT_NAME
from ..conf import ClientConfig
from pikesquares.cli.console import console
from pikesquares import read_stats

logger = logging.getLogger(__name__)


__all__ = (
    "Device",
    "Handler",
    "HandlerFactory",
    "HttpRouter",
    "HttpsRouter",
    "Project",
    "WsgiApp",
)


from svcs._core import (
    _KEY_CONTAINER,
    _KEY_REGISTRY,
    T1,
    T2,
    T3,
    T4,
    T5,
    T6,
    T7,
    T8,
    T9,
    T10,
    Container,
    Registry,
    # ServicePing,
)


def init_context(context: dict):
    context[_KEY_REGISTRY] = Registry()
    return context


def svcs_from(context: dict) -> Container:
    print(f"svcs_from: {context=}")
    if (cont := context.get(_KEY_CONTAINER, None)) is None:
        cont = Container(context[_KEY_REGISTRY])
        context[_KEY_CONTAINER] = cont

    return cont


def register_factory(
    context: dict,
    svc_type: type,
    factory: Callable,
    *,
    enter: bool = True,
    ping: Callable | None = None,
    on_registry_close: Callable | None = None,
) -> None:

    context[_KEY_REGISTRY].register_factory(
        svc_type,
        factory,
        enter=enter,
        ping=ping,
        on_registry_close=on_registry_close,
    )


@overload
def get(context: dict, svc_type: type[T1], /) -> T1: ...


@overload
def get(context: dict, svc_type1: type[T1], svc_type2: type[T2], /) -> tuple[T1, T2]: ...


@overload
def get(context: dict, svc_type1: type[T1], svc_type2: type[T2], svc_type3: type[T3], /) -> tuple[T1, T2, T3]: ...


@overload
def get(
    context: dict,
    svc_type1: type[T1],
    svc_type2: type[T2],
    svc_type3: type[T3],
    svc_type4: type[T4],
    /,
) -> tuple[T1, T2, T3, T4]: ...


@overload
def get(
    context: dict,
    svc_type1: type[T1],
    svc_type2: type[T2],
    svc_type3: type[T3],
    svc_type4: type[T4],
    svc_type5: type[T5],
    /,
) -> tuple[T1, T2, T3, T4, T5]: ...


@overload
def get(
    context: dict,
    svc_type1: type[T1],
    svc_type2: type[T2],
    svc_type3: type[T3],
    svc_type4: type[T4],
    svc_type5: type[T5],
    svc_type6: type[T6],
    /,
) -> tuple[T1, T2, T3, T4, T5, T6]: ...


@overload
def get(
    context: dict,
    svc_type1: type[T1],
    svc_type2: type[T2],
    svc_type3: type[T3],
    svc_type4: type[T4],
    svc_type5: type[T5],
    svc_type6: type[T6],
    svc_type7: type[T7],
    /,
) -> tuple[T1, T2, T3, T4, T5, T6, T7]: ...


@overload
def get(
    context: dict,
    svc_type1: type[T1],
    svc_type2: type[T2],
    svc_type3: type[T3],
    svc_type4: type[T4],
    svc_type5: type[T5],
    svc_type6: type[T6],
    svc_type7: type[T7],
    svc_type8: type[T8],
    /,
) -> tuple[T1, T2, T3, T4, T5, T6, T7, T8]: ...


@overload
def get(
    context: dict,
    svc_type1: type[T1],
    svc_type2: type[T2],
    svc_type3: type[T3],
    svc_type4: type[T4],
    svc_type5: type[T5],
    svc_type6: type[T6],
    svc_type7: type[T7],
    svc_type8: type[T8],
    svc_type9: type[T9],
    /,
) -> tuple[T1, T2, T3, T4, T5, T6, T7, T8, T9]: ...


@overload
def get(
    context: dict,
    svc_type1: type[T1],
    svc_type2: type[T2],
    svc_type3: type[T3],
    svc_type4: type[T4],
    svc_type5: type[T5],
    svc_type6: type[T6],
    svc_type7: type[T7],
    svc_type8: type[T8],
    svc_type9: type[T9],
    svc_type10: type[T10],
    /,
) -> tuple[T1, T2, T3, T4, T5, T6, T7, T8, T9, T10]: ...


def get(
    context: dict,
    *svc_types: type,
) -> object:

    print(f"svcs_get: {context=}")
    print(f"svcs_get: {svc_types=}")
    return svcs_from(context).get(*svc_types)


class BaseService(pydantic.BaseModel):

    model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)

    conf: ClientConfig
    db: TinyDB
    service_id: str
    # cache:str = "pikesquares-settings"
    parent_service_id: str | None = None
    cert_name: str = "_wildcard_pikesquares_dev"

    # cli_style: QuestionaryStyle = console.custom_style_dope

    def get_service_status(self):
        """
        read stats socket
        """
        if self.stats_address.exists() and self.stats_address.is_socket():
            return 'running' if read_stats(str(self.stats_address)) else 'stopped'

    def startup_log(self, show_config_start_marker: str, show_config_end_marker: str) -> Tuple[List, List]:
        """
        read the output of `show-config` option from the service log
        """
        with open(str(self.log_file)) as f:
            log_lines = f.readlines()
            start_index = max(idx for idx, val in enumerate(log_lines) if val == show_config_start_marker)
            end_index = max(idx for idx, val in enumerate(log_lines) if val == show_config_end_marker)
            # print(f"{start_index} {end_index}")
            latest_running_config = log_lines[start_index : end_index + 1]
            latest_startup_log = log_lines[end_index + 1 :]
        return latest_running_config, latest_startup_log

    # @pydantic.computed_field
    # def easyrsa(self) -> str:
    #    return str(Path(self.easyrsa_dir) / "EasyRSA-3.1.7" / "easyrsa")

    #@pydantic.computed_field
    #def caddy(self) -> Path | None:
    #    try:
    #        return self.caddy_dir / "caddy"
    #    except TypeError:
    #        pass

    @pydantic.computed_field
    def enable_sentry(self) -> bool:
        return self.conf.ENABLE_SENTRY

    #@pydantic.computed_field
    #def sentry_dsn(self) -> str:
    #    return self.conf.SENTRY_DSN

    @pydantic.computed_field
    def data_dir(self) -> Path:
        return self.conf.DATA_DIR

    @pydantic.computed_field
    def config_dir(self) -> Path:
        return self.conf.CONFIG_DIR

    @pydantic.computed_field
    def log_dir(self) -> Path:
        return self.conf.LOG_DIR

    @pydantic.computed_field
    def run_dir(self) -> Path:
        return self.conf.RUN_DIR

    # @pydantic.computed_field
    # def easyrsa_dir(self) -> Path:
    #    return Path(self.conf.EASYRSA_DIR)

    #@pydantic.computed_field
    #def caddy_dir(self) -> Path | None:
    #    if self.conf.CADDY_DIR and Path(self.conf.CADDY_DIR).exists():
    #        return Path(self.conf.CADDY_DIR)

    @pydantic.computed_field
    def plugins_dir(self) -> Path:
        return self.conf.PLUGINS_DIR

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / f"{self.service_id}.json"

    @pydantic.computed_field
    def stats_address(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}-stats.sock"

    @pydantic.computed_field
    def socket_address(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}.sock"

    @pydantic.computed_field
    def notify_socket(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}-notify.sock"

    @pydantic.computed_field
    def uid(self) -> int:
        return self.conf.RUN_AS_UID

    @pydantic.computed_field
    def gid(self) -> int:
        return self.conf.RUN_AS_GID

    @pydantic.computed_field
    def server_uid(self) -> int:
        return self.conf.SERVER_RUN_AS_UID

    @pydantic.computed_field
    def server_gid(self) -> int:
        return self.conf.SERVER_RUN_AS_GID

    @pydantic.computed_field
    def touch_reload_file(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / f"{self.service_id}.json"

    @pydantic.computed_field
    def pid_file(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}.pid"

    @pydantic.computed_field
    def log_file(self) -> Path:
        return Path(self.conf.LOG_DIR) / f"{self.service_id}.log"

    @pydantic.computed_field
    def fifo_file(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}-master-fifo"

    @pydantic.computed_field
    def device_db_path(self) -> Path:
        return Path(self.conf.DATA_DIR) / "device-db.json"

    @pydantic.computed_field
    def pki_dir(self) -> Path:
        return Path(self.conf.PKI_DIR)

    @pydantic.computed_field
    def certificate(self) -> Path:
        return Path(self.conf.PKI_DIR) / "issued" / f"{self.cert_name}.crt"

    @pydantic.computed_field
    def certificate_key(self) -> Path:
        return Path(self.conf.PKI_DIR) / "private" / f"{self.cert_name}.key"

    @pydantic.computed_field
    def certificate_ca(self) -> Path:
        return Path(self.conf.PKI_DIR) / "ca.crt"


class Device(BaseService):

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / "device.json"

    @pydantic.computed_field
    def spooler_dir(self) -> Path:
        dir = Path(self.conf.DATA_DIR) / "spooler"
        if dir and not dir.exists():
            dir.mkdir(parents=True, exist_ok=True)
        return dir

    @pydantic.computed_field
    def apps_dir(self) -> Path:
        dir = Path(self.conf.CONFIG_DIR) / "projects"
        if dir and not dir.exists():
            dir.mkdir(parents=True, exist_ok=True)
        return dir

    # def __init__(self, conf, *args, **kwargs):
    #    self.conf = conf

    # super().__init__(*args, **kwargs)

    # def up(self):
    #    device = HandlerFactory.make_handler("Device")(
    #        service_id="device",
    #        conf=self.conf,
    #    )
    #    device.prepare_service_config()
    #    device.start()


class Project(BaseService):
    pass

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / "projects" / f"{self.service_id}.json"

    @pydantic.computed_field
    def apps_dir(self) -> str:
        apps_dir = Path(self.conf.CONFIG_DIR) / f"{self.service_id}" / "apps"
        if apps_dir and not apps_dir.exists():
            apps_dir.mkdir(parents=True, exist_ok=True)
        return str(apps_dir.resolve())


class HttpsRouter(BaseService):
    pass

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / "projects" / f"{self.service_id}.json"

    @pydantic.computed_field
    def socket_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=3017)}"

        # @pydantic.computed_field
        # def stats_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=9897)}"

    @pydantic.computed_field
    def subscription_server_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=5600)}"

    @pydantic.computed_field
    def resubscribe_to(self) -> Path:
        # resubscribe_to: str = None,
        return Path()


class HttpRouter(BaseService):
    pass

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / "projects" / f"{self.service_id}.json"

    @pydantic.computed_field
    def socket_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=4017)}"

        # @pydantic.computed_field
        # def stats_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=9897)}"

    @pydantic.computed_field
    def subscription_server_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=6600)}"

    @pydantic.computed_field
    def resubscribe_to(self) -> Path:
        # resubscribe_to: str = None,
        return Path()


class WsgiApp(BaseService):

    name: str

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / f"{self.parent_service_id}" / "apps" / f"{self.service_id}.json"

    @pydantic.computed_field
    def touch_reload_file(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / f"{self.parent_service_id}" / "apps" / f"{self.service_id}.json"

    @pydantic.computed_field
    def socket_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=4017)}"


class ManagedDaemon(BaseService):

    name: str
    command: str

    # @pydantic.computed_field
    # def service_config(self) -> Path:
    #    return Path(self.conf.CONFIG_DIR) / \
    #            f"{self.parent_service_id}" / "apps" \
    #            / f"{self.service_id}.json"

    # @pydantic.computed_field
    # def touch_reload_file(self) -> Path:
    #    return Path(self.conf.CONFIG_DIR) / \
    #            f"{self.parent_service_id}" / "apps" \
    #            / f"{self.service_id}.json"

    # @pydantic.computed_field
    # def socket_address(self) -> str:
    #    return f"127.0.0.1:{get_first_available_port(port=4017)}"


class Handler(Protocol):

    svc_model: BaseService

    def __init__(
        self,
        svc_model: BaseService,
        is_internal: bool = True,
        is_enabled: bool = False,
        is_app: bool = False,
        name: str = "",
    ):
        self.svc_model = svc_model

        # if self.svc_model.enable_sentry and self.svc_model.sentry_dsn:
        #    try:
        #        import sentry_sdk
        #        from pikesquares import __version__, __app_name__
        #    except ImportError:
        #        pass
        #    else:
        #        sentry_sdk.init(
        #            dsn=self.svc_model.sentry_dsn,
        #            traces_sample_rate=1.0,
        #            release=f"{__app_name__} v{__version__}",
        #        )
                # console.success("initialized sentry-sdk")

    # def is_started(self):
    #    return get_service_status(
    #            self.svc_model.service_id, self.svc_model.conf
    #    ) == "running"

    @abstractmethod
    def connect(self):
        raise NotImplementedError

    @abstractmethod
    def prepare_service_config(self):
        raise NotImplementedError

    @abstractmethod
    def start(self):
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        raise NotImplementedError

    def write_master_fifo(self, command: str) -> None:
        """
        Write command to master fifo named pipe

        ‘0’ to ‘9’ - set the fifo slot (see below)
        ‘+’ - increase the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
        ‘-’ - decrease the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
        ‘B’ - ask Emperor for reinforcement (broodlord mode, requires uWSGI >= 2.0.7)
        ‘C’ - set cheap mode
        ‘c’ - trigger chain reload
        ‘E’ - trigger an Emperor rescan
        ‘f’ - re-fork the master (dangerous, but very powerful)
        ‘l’ - reopen log file (need –log-master and –logto/–logto2)
        ‘L’ - trigger log rotation (need –log-master and –logto/–logto2)
        ‘p’ - pause/resume the instance
        ‘P’ - update pidfiles (can be useful after master re-fork)
        ‘Q’ - brutally shutdown the instance
        ‘q’ - gracefully shutdown the instance
        ‘R’ - send brutal reload
        ‘r’ - send graceful reload
        ‘S’ - block/unblock subscriptions
        ‘s’ - print stats in the logs
        ‘W’ - brutally reload workers
        ‘w’ - gracefully reload workers
        """

        if not command in ["r", "q", "s"]:
            console.warning("unknown master fifo command '{command}'")
            return

        if not all(
            [
                self.svc_model.fifo_file,
                self.svc_model.fifo_file.exists(),
            ]
        ):
            console.warning(f"invalid fifo file @ {self.svc_model.fifo_file}")
            return

        with open(str(self.svc_model.fifo_file), "w") as master_fifo:
            master_fifo.write(command)
            console.info(f"[pikesquares-services] : sent command [{command}] to master fifo")

    @property
    def handler_name(self):
        return self.__class__.__name__

    def __repr__(self):
        return self.handler_name

    def __str__(self):
        return self.handler_name

    def log(self, message):
        uwsgi.log(f"[pikesquares-services] : {self.handler_name}] {message}")


class HandlerFactory:
    handlers = {}

    @classmethod
    def user_visible_apps(cls):
        return {
            k
            for k in cls.handlers
            if all(
                [
                    cls.handlers[k].is_internal == False,
                    cls.handlers[k].is_enabled == True,
                    cls.handlers[k].is_app == True,
                ]
            )
        }

    @classmethod
    def make_handler(cls, name):
        try:
            retval = cls.handlers[name]
        except KeyError as err:
            raise NotImplementedError(f"{name=} doesn't exist") from err
        return retval

    @classmethod
    def register(cls, type_name):
        def deco(deco_cls):
            cls.handlers[type_name] = deco_cls
            print(f"registered {type_name} {deco_cls}")
            return deco_cls
        return deco


# @HandlerFactory.register('WSGI-App')
# class WSGIAppHandler(Handler):

# @HandlerFactory.register('Managed-Service')
# class WSGIAppHandler(Handler):
