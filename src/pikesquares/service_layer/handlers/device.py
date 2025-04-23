import structlog
from cuid import cuid

from pikesquares import services
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
    create_kwargs: dict,
) -> Device | None:

    machine_id = await ServiceBase.read_machine_id()
    if not machine_id:
        raise AppConfigError("unable to read the machine-id")

    uow = await services.aget(context, UnitOfWork)
    device = await uow.devices.get_by_machine_id(machine_id)
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
        try:
            device = await uow.devices.add(device)
            zmq_monitor = await get_or_create_zmq_monitor(uow, device=device)
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
            _ = await get_or_create_http_router("default-http-router", context)
            _ = await get_or_create_project("default-project", context)

            # if device.enable_dir_monitor:
            #    try:
            #        uwsgi_config = device.write_uwsgi_config()
            #    except PermissionError:
            #        logger.error("permission denied writing project uwsgi config to disk")
            #    else:
            #        logger.debug(f"wrote config to file: {uwsgi_config}")
            await uow.commit()
        except Exception as exc:
            logger.exception(exc)
            await uow.rollback()

    return device
