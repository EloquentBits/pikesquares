import structlog
from cuid import cuid

from pikesquares.conf import AppConfigError
from pikesquares.domain.base import ServiceBase
from pikesquares.domain.device import Device
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.service_layer.handlers.routers import get_or_create_http_router
from pikesquares.service_layer.handlers.project import get_or_create_project


logger = structlog.getLogger()


async def get_or_create_device(
    context: dict,
    uow: UnitOfWork,
    create_kwargs: dict,
) -> Device:

    machine_id = await ServiceBase.read_machine_id()
    if not machine_id:
        raise AppConfigError("unable to read the machine-id")

    device = await uow.devices.get_by_machine_id(machine_id)
    if not device:
        uwsgi_plugins = []
        if create_kwargs.get("enable_tuntap_router"):
            uwsgi_plugins.append("tuntap")

        if create_kwargs.get("enable_zeromq_monitor"):
            uwsgi_plugins.append("emperor_zeromq")

        device = Device(
            service_id=f"device_{cuid()}",
            uwsgi_plugins=", ".join(uwsgi_plugins),
            machine_id=machine_id,
            **create_kwargs,
        )
        # device.routers.add(default_http_router)
        device = await uow.devices.add(device)
        await uow.commit()
        logger.debug(f"Created {device=} for {machine_id=}")

    default_http_router = await get_or_create_http_router("default-http-router", device, uow, create_kwargs)
    context["default-http-router"] = default_http_router

    default_project = await get_or_create_project("default-project", device, uow, create_kwargs)
    context["default-project"] = default_project

    if device.enable_dir_monitor:
        try:
            uwsgi_config = device.write_uwsgi_config()
        except PermissionError:
            logger.error("permission denied writing project uwsgi config to disk")
        else:
            logger.debug(f"wrote config to file: {uwsgi_config}")
    # await device.sync_db_with_filesystem(uow)
    return device
