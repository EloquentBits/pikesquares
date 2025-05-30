import cuid
import structlog

from pikesquares.domain.device import Device
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.conf import AppConfigError

logger = structlog.getLogger()


async def provision_device(uow: UnitOfWork, create_kwargs: dict) -> Device:
    try:
        machine_id = await Device.read_machine_id()
        if not machine_id:
            raise AppConfigError("unable to read the machine-id")

        device = Device(
            service_id=f"device-{cuid.slug()}",
            uwsgi_plugins="emperor_zeromq",
            machine_id=machine_id,
            **create_kwargs,
        )
        device = await uow.devices.add(device)
    except Exception as exc:
        logger.info("failed provisioning device")
        logger.exception(exc)
        raise exc

    return device
