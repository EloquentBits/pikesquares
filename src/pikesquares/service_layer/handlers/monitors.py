import structlog
from aiopath import AsyncPath

from pikesquares.domain.device import Device
from pikesquares.domain.monitors import ZMQMonitor

from pikesquares.domain.project import Project
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def get_or_create_zmq_monitor(
    uow: UnitOfWork,
    device: Device | None = None,
    project: Project | None = None,
) -> ZMQMonitor | None:
    zmq_monitor = None

    if device:
        zmq_monitor = await uow.zmq_monitors.get_by_device_id(device.id)
    elif project:
        zmq_monitor = await uow.zmq_monitors.get_by_project_id(project.id)

    if not zmq_monitor:
        create_kwargs: dict[str, str | Project | Device] = {
            "transport": "ipc",
        }
        if device:
            create_kwargs["device"] = device
            create_kwargs["socket"] = str(AsyncPath(device.run_dir) / f"{device.service_id}-zmq-monitor.sock")

        if project:
            create_kwargs["project"] = project
            create_kwargs["socket"] = str(AsyncPath(project.run_dir) / f"{project.service_id}-zmq-monitor.sock")

        zmq_monitor = ZMQMonitor(**create_kwargs)
        try:
            await uow.zmq_monitors.add(zmq_monitor)
            await uow.commit()
            logger.debug(f"Created {zmq_monitor} ")
        except Exception as exc:
            logger.exception(exc)
            await uow.rollback()
    else:
        logger.debug(f"Using existing zmq_monitor {zmq_monitor}")

    # if project.enable_dir_monitor:
    #    if not await AsyncPath(project.apps_dir).exists():
    #        await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)
    #    uwsgi_config = project.write_uwsgi_config()
    #    logger.debug(f"wrote config to file: {uwsgi_config}")

    return zmq_monitor
