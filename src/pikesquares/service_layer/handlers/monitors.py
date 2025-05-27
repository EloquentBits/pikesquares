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
) -> ZMQMonitor | None:
    try:
        create_kwargs: dict = {
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
    except Exception as exc:
        raise exc

    return zmq_monitor


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

