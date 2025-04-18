import pytest
from testfixtures import TempDirectory
from aiopath import AsyncPath
from pikesquares.domain.monitors import ZMQMonitor
from pikesquares.service_layer.handlers.monitors import get_or_create_zmq_monitor

class FakeRepository:
    def __init__(self, existing_zmq_monitor: ZMQMonitor | None = None):
        self._zmq_monitor = existing_zmq_monitor
        self.added_zmq_monitor = None

    async def get_by_transport(self, transport: str) -> ZMQMonitor | None:
        return self._zmq_monitor

    async def add(self, zmq_monitor: ZMQMonitor):
        self.added_zmq_monitor = zmq_monitor


class FakeUoW:
    def __init__(self, zmq_monitor: ZMQMonitor | None = None):
        self.zmq_monitors = FakeRepository(existing_zmq_monitor=zmq_monitor)
        self.committed = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


# Positive
@pytest.mark.asyncio
async def test_creates_zmq_monitor():
    with TempDirectory() as tmp:
        uow = FakeUoW()
        socket = AsyncPath(tmp.path) / "monitor.sock"

        zmq_monitor = await get_or_create_zmq_monitor(uow, socket)

        assert uow.committed
        assert zmq_monitor.transport == "ipc"
        assert zmq_monitor.socket == str(socket)
        assert uow.zmq_monitors.added_zmq_monitor is not None
        assert uow.zmq_monitors.added_zmq_monitor.transport == "ipc"
        assert uow.zmq_monitors.added_zmq_monitor.socket == str(socket)


@pytest.mark.asyncio
async def test_get_zmq_monitor():
    existing = ZMQMonitor(
        id="monitor_123",
        socket="/tmp/existing_monitor.sock",
        transport="ipc",
    )

    uow = FakeUoW(zmq_monitor=existing)
    socket = AsyncPath("/tmp/monitor.sock")

    zmq_monitor = await get_or_create_zmq_monitor(uow, socket)

    assert zmq_monitor is existing
    assert uow.zmq_monitors.added_zmq_monitor is None
    assert uow.committed is False
    
# Negative   
@pytest.mark.asyncio
async def test_none_uow():
    with TempDirectory() as tmp:
        socket = AsyncPath(tmp.path) / "monitor.sock"

        with pytest.raises(AttributeError):
            await get_or_create_zmq_monitor(None, socket)
            

            
        