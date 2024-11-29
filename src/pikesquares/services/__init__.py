import logging
from typing import overload, NewType
from collections.abc import Callable

from tinydb import TinyDB

from pikesquares import conf
#from pikesquares.services.device import Device
#from pikesquares.services.app import WsgiApp
#from pikesquares.services.router import HttpRouter, HttpsRouter

logger = logging.getLogger(__name__)


__all__ = (
    # "Device",
    # "HttpRouter",
    # "HttpsRouter",
    # "Project",
    # "WsgiApp",
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
    ServicePing,
)


def init_context(context: dict):
    context[_KEY_REGISTRY] = Registry()
    return context


def svcs_from(context: dict) -> Container:
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


def register_value(
    context: dict,
    svc_type: type,
    value: object,
    *,
    enter: bool = False,
    ping: Callable | None = None,
    on_registry_close: Callable | None = None,
) -> None:
    """
    Same as :meth:`svcs.Registry.register_value()`, but uses registry on *app*
    that has been put there by :func:`init_app()`.
    """
    context[_KEY_REGISTRY].register_value(
        svc_type,
        value,
        enter=enter,
        ping=ping,
        on_registry_close=on_registry_close,
    )



def get_pings(context: dict) -> list[ServicePing]:
    return svcs_from(context).get_pings()


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
    return svcs_from(context).get(*svc_types)

#####################################
####### init app


def init_app(cli_context):
    context = init_context(cli_context)
    return context


def register_app_conf(context, conf_mapping):
    def conf_factory():
        return conf.ClientConfig(**conf_mapping)
    register_factory(context, conf.ClientConfig, conf_factory)


def register_db(context, db_path):
    def tinydb_factory():
        with TinyDB(db_path) as db:
            yield db
    register_factory(context, TinyDB, tinydb_factory)


def register_device(context, device_class):
    def device_factory():
        data = {
            "conf": get(context, conf.ClientConfig),
            "db": get(context, TinyDB),
            "service_id": "device",
        }
        return device_class(**data)
    register_factory(
        context,
        device_class,
        device_factory,
        ping=lambda svc: svc.ping()
    )


def register_wsgi_app(context, app_class, service_id):
    def app_factory():
        data = {
            "conf": get(context, conf.ClientConfig),
            "db": get(context, TinyDB),
            "service_id": service_id,
        }
        return app_class(**data)
    register_factory(context, app_class, app_factory)


def register_project(context, project_class, service_id):
    def project_factory():
        data = {
            "conf": get(context, conf.ClientConfig),
            "db": get(context, TinyDB),
            "service_id": service_id,
        }
        return project_class(**data)
    register_factory(context, project_class, project_factory)


def register_sandbox_project(context, proj_type, proj_class):
    def sandbox_project_factory():
        return proj_class(
            conf=get(context, conf.ClientConfig),
            db=get(context, TinyDB),
            service_id="project_sandbox",
        )
    register_factory(context, proj_type, sandbox_project_factory)


def register_default_router(context, address: str, router_class):
    def default_router_factory():
        router_alias = "https" if "https" in router_class.__name__.lower() else "http"
        return router_class(
            address=address,
            conf=get(context, conf.ClientConfig),
            db=get(context, TinyDB),
            service_id=f"default_{router_alias}_router",
        )
    register_factory(context, router_class, default_router_factory)


# def register_pc_api(context):
#    def pc_api_factory():
#        return "http://127.0.0.1:9555/"
#    register_factory(context, device_class, device_factory)
