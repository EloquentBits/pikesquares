import pytest
from aiopath import AsyncPath

from pikesquares.service_layer.handlers import monitors
from pikesquares.domain.monitors import ZMQMonitor
from pikesquares.service_layer.handlers.monitors import get_or_create_zmq_monitor



class FakeRepository:
    def __init__(self, existing_zmq_monitor: ZMQMonitor | None = None):
        self._zmq_monitor = existing_zmq_monitor
        self.added_zmq_monitor = None
        self._session = None

    async def get_by_project_id(self, project_id: str) -> ZMQMonitor | None:
        return self._zmq_monitor

    async def add(self, zmq_monitor: ZMQMonitor):
        self.added_zmq_monitor = zmq_monitor
        self._session.add(zmq_monitor)
        await self._session.flush()
        await self._session.refresh(zmq_monitor)


class FakeUnitOfWork:
    def __init__(self, zmq_monitor: ZMQMonitor | None = None):
        self.zmq_monitors = FakeRepository(existing_zmq_monitor=zmq_monitor)
        self.committed = False
        self.rolled_back = False 
        self._session = FakeSession()
        self.zmq_monitors._session = self._session

    async def commit(self):
        self.committed = True
        await self._session.commit()

    async def rollback(self):
        self.rolled_back = True

    async def __aenter__(self):
        return self

    async def __aexit__(self):
        pass


class FakeSession:
    def __init__(self):
        self.commit_called = False
        self.flush_called = False
        self.refreshed_objects = []
        self.added_objects = []

    async def commit(self):
        self.commit_called = True

    async def flush(self):
        self.flush_called = True

    async def refresh(self, obj):
        self.refreshed_objects.append(obj)

    def add(self, obj):
        self.added_objects.append(obj)
        

# Positive
@pytest.mark.asyncio
async def test_creates_zmq_monitor(project, run_dir):
    
    uow = FakeUnitOfWork()
    expected_socket = str(AsyncPath(run_dir.path) / f"{project.service_id}-zmq-monitor.sock")

    zmq_monitor = await get_or_create_zmq_monitor(uow, project=project)

    assert uow.committed is True
    assert zmq_monitor is not None
    assert isinstance(zmq_monitor, ZMQMonitor)
    assert zmq_monitor.transport == "ipc"
    assert zmq_monitor.socket == expected_socket
    assert uow.zmq_monitors.added_zmq_monitor is zmq_monitor

    

@pytest.mark.asyncio
async def test_get_zmq_monitor(project, device_zmq_monitor):

    uow = FakeUnitOfWork(zmq_monitor=device_zmq_monitor)
    zmq_monitor = await get_or_create_zmq_monitor(uow, project=project)

    assert uow.committed is False
    assert zmq_monitor is zmq_monitor
    assert uow.zmq_monitors.added_zmq_monitor is None


# Negative
@pytest.mark.asyncio
async def test_creates_zmq_monitor_rollback(project, mocker):

    uow = FakeUnitOfWork()
    uow.zmq_monitors._session = uow._session
    mocker.patch.object(uow.zmq_monitors, "add", side_effect=Exception("DB write error"))
    monitors.logger.exception = lambda exc: None  

    zmq_monitor = await get_or_create_zmq_monitor(uow, project=project)

    # assert zmq_monitor is  None
    assert uow.rolled_back is True 
    assert uow.committed is False  
    assert uow.zmq_monitors.added_zmq_monitor is None
