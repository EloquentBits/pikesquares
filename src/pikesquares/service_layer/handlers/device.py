import structlog
from cuid import cuid
from aiopath import AsyncPath

from pikesquares.conf import AppConfigError
from pikesquares.domain.base import ServiceBase
from pikesquares.domain.device import Device
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.service_layer.handlers.routers import get_or_create_http_router
from pikesquares.service_layer.handlers.project import get_or_create_project
from pikesquares.service_layer.handlers.monitors import get_or_create_zmq_monitor


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
    device_created: bool = not device
    if not device:
        device_cuid = f"device_{cuid()}"
        uwsgi_plugins = []
        if create_kwargs.get("enable_tuntap_router"):
            uwsgi_plugins.append("tuntap")

        uwsgi_plugins.append("emperor_zeromq")

        device = Device(
            service_id=device_cuid,
            uwsgi_plugins=", ".join(uwsgi_plugins),
            machine_id=machine_id,
            **create_kwargs,
        )
        device = await uow.devices.add(device)
        logger.debug(f"Created {device=} for {machine_id=}")

        zmq_monitor = await get_or_create_zmq_monitor(uow, device=device)
        context["device-zmq-monitor"] = zmq_monitor
        device.zmq_monitor = zmq_monitor
        # uwsgi_options = await uow.uwsgi_options.get_by_device_id(device.id)
        # if not uwsgi_options:
        for uwsgi_option in device.get_uwsgi_options():
            await uow.uwsgi_options.add(uwsgi_option)
            """
            existing_options = await uow.uwsgi_options.list(device_id=device.id)
            for uwsgi_option in device.build_uwsgi_options():
                #existing_options
                #if uwsgi_option.option_key
                #not in existing_options:
                #    await uow.uwsgi_options.add(uwsgi_option)
            """

        # device.routers.add(default_http_router)

    default_http_router, http_router_created = await get_or_create_http_router(
        "default-http-router", device, uow, create_kwargs
    )
    context["default-http-router"] = default_http_router

    default_project, default_project_created = await get_or_create_project(
        "default-project", device, uow, create_kwargs
    )
    context["default-project"] = default_project

    if device.enable_dir_monitor:
        try:
            uwsgi_config = device.write_uwsgi_config()
        except PermissionError:
            logger.error("permission denied writing project uwsgi config to disk")
        else:
            logger.debug(f"wrote config to file: {uwsgi_config}")

    if any([device_created, http_router_created, default_project_created]):
        await uow.commit()

    return device
