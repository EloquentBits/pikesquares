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

    #if device:
    #    zmq_monitor = await uow.zmq_monitors.get_by_device_id(device.id)
    #elif project:
    #    zmq_monitor = await uow.zmq_monitors.get_by_project_id(project.id)

    #if not zmq_monitor:
    try:
        create_kwargs: dict[str, str | Project | Device] = {
            "transport": "ipc",
        }
        if device:
            create_kwargs["device"] = device
            create_kwargs["socket"] = str(device.zmq_monitor_socket)

        if project:
            create_kwargs["project"] = project
            create_kwargs["socket"] = str(project.zmq_monitor_socket)

        zmq_monitor = ZMQMonitor(**create_kwargs)
        await uow.zmq_monitors.add(zmq_monitor)
        logger.debug(f"Created {zmq_monitor} ")
    except Exception as exc:
        raise exc

    # if project.enable_dir_monitor:
    #    if not await AsyncPath(project.apps_dir).exists():
    #        await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)
    #    uwsgi_config = project.write_uwsgi_config()
    #    logger.debug(f"wrote config to file: {uwsgi_config}")

    return zmq_monitor


async def create_or_restart_instance(zmq_monitor_address: str, name: str, uwsgi_config: str) -> None:
    logger.info(f"{zmq_monitor_address=}")
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.PUSH)
    sock.connect(zmq_monitor_address)
    await sock.send_multipart([b"touch", name.encode(), uwsgi_config.encode()])

async def destroy_instance(zmq_monitor_address: str, name: str, model: Device | Project) -> None:
    logger.info(f"{zmq_monitor_address=}")
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.PUSH)
    sock.connect(zmq_monitor_address)
    await sock.send_multipart([b"destroy", name.encode()])

