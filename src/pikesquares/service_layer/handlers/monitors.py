import structlog
from aiopath import AsyncPath
import zmq
import zmq.asyncio

from pikesquares.domain.device import Device
from pikesquares.domain.monitors import ZMQMonitor

from pikesquares.domain.project import Project
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.domain.wsgi_app import WsgiApp

logger = structlog.getLogger()


async def create_zmq_monitor(
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
            logger.debug(f"Created {zmq_monitor} ")
        except Exception as exc:
            raise exc
    else:
        logger.debug(f"Using existing zmq_monitor {zmq_monitor}")

    # if project.enable_dir_monitor:
    #    if not await AsyncPath(project.apps_dir).exists():
    #        await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)
    #    uwsgi_config = project.write_uwsgi_config()
    #    logger.debug(f"wrote config to file: {uwsgi_config}")

    return zmq_monitor


async def create_or_restart_instance(zmq_monitor: ZMQMonitor, name: str, uwsgi_config: str) -> None:

    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.PUSH)
    if zmq_monitor.zmq_address:
        #logger.debug(f"Launching {model.__class__.__name__} {model.service_id} in ZMQ Monitor @ {zmq_monitor.zmq_address}")

        logger.debug(uwsgi_config)
        sock.connect(zmq_monitor.zmq_address)
        await sock.send_multipart([b"touch", name.encode(), uwsgi_config.format(do_print=True).encode()])
    else:
        logger.info(f"no zmq socket found @ {zmq_monitor.zmq_address}")

async def destroy_instance(zmq_monitor: ZMQMonitor, name: str, model: Device | Project) -> None:
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.PUSH)
    if zmq_monitor.zmq_address:
        sock.connect(zmq_monitor.zmq_address)
        logger.debug(f"Stopping {model.__class__.__name__} {model.service_id} in ZMQ Monitor @ {zmq_monitor.zmq_address}")
        await sock.send_multipart([b"destroy", name.encode()])

