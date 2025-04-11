import structlog
from aiopath import AsyncPath

# from pikesquares.domain.device import Device
from pikesquares.domain.monitors import ZMQMonitor

# from pikesquares.domain.project import Project
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def get_or_create_zmq_monitor(
    uow: UnitOfWork,
    socket: AsyncPath,
    # device: Device | None = None,
    # project: Project | None = None,
) -> ZMQMonitor:

    zmq_monitor = await uow.zmq_monitors.get_by_transport("ipc")

    if not zmq_monitor:
        zmq_monitor = ZMQMonitor(
            socket=str(socket),
            transport="ipc",
            # device=device,
            # project=project,
        )
        await uow.zmq_monitors.add(zmq_monitor)
        await uow.commit()
        logger.debug(f"Created {zmq_monitor} ")
    else:
        logger.debug(f"Using existing zmq_monitor {zmq_monitor}")

    # if project.enable_dir_monitor:
    #    if not await AsyncPath(project.apps_dir).exists():
    #        await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)
    #    uwsgi_config = project.write_uwsgi_config()
    #    logger.debug(f"wrote config to file: {uwsgi_config}")

    return zmq_monitor
