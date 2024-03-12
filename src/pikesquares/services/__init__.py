import logging
from typing import Protocol
from abc import abstractmethod
from pathlib import Path

import pydantic
from uwsgiconf import uwsgi

from .. import (
    #PathLike,
    get_first_available_port,
    get_service_status,
)
from ..cli.pki import CERT_NAME
from ..conf import ClientConfig

logger = logging.getLogger(__name__)


class BaseService(pydantic.BaseModel):

    service_id:str
    conf: ClientConfig
    cache:str = "pikesquares-settings"
    parent_service_id:str = ""

    @property
    def run_dir(self) -> Path:
        return Path(self.conf.RUN_DIR)

    @property
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / f"{self.service_id}.json"

    @property
    def stats_address(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}-stats.sock"

    @property
    def socket_address(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}.sock"

    @property
    def notify_socket(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}-notify.sock"

    @property
    def uid(self) -> int:
        return self.conf.RUN_AS_UID

    @property
    def gid(self) -> int:
        return self.conf.RUN_AS_GID

    @property
    def touch_reload_file(self) -> Path:
        return self.service_config

    @property
    def pid_file(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}.pid"

    @property
    def log_file(self) -> Path:
        return Path(self.conf.LOG_DIR) / f"{self.service_id}.log"

    @property
    def fifo_file(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}-master-fifo"

    @property
    def device_db_path(self) -> Path:
        return Path(self.conf.DATA_DIR) / 'device-db.json'

    @property
    def certificate(self) -> Path:
        return Path(self.conf.PKI_DIR) / "issued" / f"{CERT_NAME}.crt"

    @property
    def certificate_key(self) -> Path:
        return Path(self.conf.PKI_DIR) / "private" / f"{CERT_NAME}.key"

    @property
    def client_ca(self) -> Path:
        return Path(self.conf.PKI_DIR) / "ca.crt"


        

class Device(BaseService):
    pass

    @property
    def service_config(self):
        return Path(self.conf.CONFIG_DIR) / 'device.json'

    @property
    def spooler_dir(self) -> Path:
        dir = Path(self.conf.DATA_DIR) / 'spooler'
        if dir and not dir.exists():
            dir.mkdir(parents=True, exist_ok=True)
        return dir

    @property
    def apps_dir(self) -> Path:
        dir = Path(self.conf.CONFIG_DIR) / "projects"
        if dir and not dir.exists():
            dir.mkdir(parents=True, exist_ok=True)
        return dir

    #def __init__(self, conf, *args, **kwargs):
    #    self.conf = conf

        #super().__init__(*args, **kwargs)

    #def up(self):
    #    device = HandlerFactory.make_handler("Device")(
    #        service_id="device", 
    #        conf=self.conf,
    #    )
    #    device.prepare_service_config()
    #    device.start()


class Project(BaseService):
    pass

    @property
    def service_config(self):
        return Path(self.conf.CONFIG_DIR) / "projects" / f"{self.service_id}.json"

    @property
    def apps_dir(self) -> str:
        apps_dir = Path(self.conf.CONFIG_DIR) / f"{self.service_id}" / "apps"
        if apps_dir and not apps_dir.exists():
            apps_dir.mkdir(parents=True, exist_ok=True)
        return str(apps_dir.resolve())

class HttpsRouter(BaseService):
    pass

    @property
    def service_config(self):
        return Path(self.conf.CONFIG_DIR) / "projects" / f"{self.service_id}.json"

    @property
    def socket_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=3017)}"

    @property
    def stats_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=9897)}"

    @property
    def subscription_server_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=5600)}"

    @property
    def resubscribe_to(self) -> Path:
        #resubscribe_to: str = None,
        return Path()



class WsgiApp(BaseService):

    name: str
    project_id: str
    root_dir: Path
    wsgi_module: str
    wsgi_file: str
    router_id: str
    pyvenv_dir: str

    @property
    def service_config(self):
        # FIXME use cuid instread of app name
        return Path(self.conf.CONFIG_DIR) / \
                f"{self.project_id}" / "apps" \
                / f"{self.service_id}.json"

    @property
    def socket_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=4017)}"



class Handler(Protocol):

    svc_model: BaseService

    def __init__(self,
            svc_model,
            is_internal: bool = True,
            is_enabled: bool = False,
            is_app: bool = False,

        ):
        self.svc_model = svc_model

    def is_started(self):
        return get_service_status(self.svc_model.service_id, self.svc_model.conf) == "running"

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

    def write_fifo(self, command: str) -> None:
        with open(self.svc_model.fifo_file, "w") as master_fifo:
           master_fifo.write(command)
           uwsgi.log(f"[pikesquares-services] : sent command [{command}] to master fifo")

    @property
    def default_options(self):
        return {}

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
            if all([
                cls.handlers[k].is_internal == False,
                cls.handlers[k].is_enabled == True,
                cls.handlers[k].is_app == True]
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
            return deco_cls
        return deco

#@HandlerFactory.register('WSGI-App')
#class WSGIAppHandler(Handler):

#@HandlerFactory.register('Managed-Service')
#class WSGIAppHandler(Handler):
