import logging
from typing import Protocol
from abc import abstractmethod
from pathlib import Path

from uwsgiconf import uwsgi

from .. import (
    PathLike, 
    get_first_available_port,
    get_service_status,
)
from ..conf import ClientConfig


logger = logging.getLogger(__name__)


class Handler(Protocol):

    service_id:str
    client_config: ClientConfig
    cache:str = "pikesquares-settings"
    config_name: str = ""
    parent_service_id:str = ""
    address: str = ""
    service_config: PathLike = None
    device_db_path: Path

    def __init__(self,
            service_id:str, 
            client_config: ClientConfig, 
            service_config: PathLike = None,
            parent_service_id:str = "",
            is_internal: bool = True,
            is_enabled: bool = False,

        ):
        self.client_config = client_config
        self.service_id = service_id
        self.parent_service_id = parent_service_id
        self.config_name = f"{service_id}.json"
        self.device_db_path = Path(self.client_config.DATA_DIR) / 'device-db.json'


    def setup_address(self, port: int = 5500) -> None:
        if not self.address:
            self.address = f"127.0.0.1:{get_first_available_port(port)}"
    
    def is_started(self):
        return get_service_status(self.service_id, self.client_config) == "running"

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
    def user_visible_services(cls):
        return {
            k
            for k in cls.handlers
            if cls.handlers[k].is_internal == False and cls.handlers[k].is_enabled == True
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

