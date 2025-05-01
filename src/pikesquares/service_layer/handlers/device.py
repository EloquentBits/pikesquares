import structlog
from cuid import cuid

from pikesquares.domain.device import Device
from pikesquares.service_layer.uow import UnitOfWork


logger = structlog.getLogger()


async def create_device(
    context: dict,
    uow: UnitOfWork,
    machine_id: str,
    create_kwargs: dict = dict(),
) -> Device:

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
        # device.zmq_monitor = zmq_monitor
        # uwsgi_options = await uow.uwsgi_options.get_by_device_id(device.id)
        # if device.enable_dir_monitor:
        #    try:
        #        uwsgi_config = device.write_uwsgi_config()
        #    except PermissionError:
        #        logger.error("permission denied writing project uwsgi config to disk")
        #    else:
        #        logger.debug(f"wrote config to file: {uwsgi_config}")
    except Exception as exc:
        raise exc

    return device
