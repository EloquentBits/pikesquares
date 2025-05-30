import structlog
import zmq
import zmq.asyncio

from pikesquares.domain.device import Device
from pikesquares.domain.monitors import ZMQMonitor
from pikesquares.domain.project import Project
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def create_zmq_monitor(
    uow: UnitOfWork,
    device: Device | None = None,
    project: Project | None = None,
) -> ZMQMonitor:
    try:
        create_kwargs: dict[str, str | Project | Device] = {"transport": "ipc"}
        if device:
            create_kwargs["device"] = device
            create_kwargs["socket_address"] = str(device.zmq_monitor_socket)
        if project:
            create_kwargs["project"] = project
            create_kwargs["socket_address"] = str(project.zmq_monitor_socket)
        logger.info(f"creating zmq monitor @ {create_kwargs.get('socket_address')}")
        zmq_monitor = ZMQMonitor(**create_kwargs)
        await uow.zmq_monitors.add(zmq_monitor)
        return zmq_monitor
    except Exception as exc:
        logger.error("unable to create zmq monitor")
        raise exc

async def create_or_restart_instance(zmq_monitor_address: str, name: str, uwsgi_config: str) -> None:
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.PUSH)
    sock.connect(zmq_monitor_address)
    await sock.send_multipart([b"touch", name.encode(), uwsgi_config.encode()])

async def destroy_instance(zmq_monitor_address: str, name: str) -> None:
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.PUSH)
    sock.connect(zmq_monitor_address)
    await sock.send_multipart([b"destroy", name.encode()])

