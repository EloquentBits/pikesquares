import pytest
from aiopath import AsyncPath
from pikesquares.domain.monitors import ZMQMonitor
from pikesquares.service_layer.handlers.monitors import create_zmq_monitor

class FakeRepository:
    def __init__(self, existing_zmq_monitor: ZMQMonitor | None = None):
        self._zmq_monitor = existing_zmq_monitor
        self.added_zmq_monitor = None
        self._session = None

    async def get_by_project_id(self, project_id: str) -> ZMQMonitor | None:
        return self._zmq_monitor

    async def get_by_device_id(self, device_id: str) -> ZMQMonitor | None:
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


@pytest.mark.asyncio
async def test_create_zmq_monitor_with_project(project):

    uow = FakeUnitOfWork()
    expected_socket = str(AsyncPath(project.run_dir) / f"{project.service_id}-zmq-monitor.sock")

    zmq_monitor = await create_zmq_monitor(uow, project=project)

    assert zmq_monitor is not None
    assert isinstance(zmq_monitor, ZMQMonitor)
    assert zmq_monitor.transport == "ipc"
    assert zmq_monitor.socket == expected_socket
    assert zmq_monitor.project == project
    assert uow.zmq_monitors.added_zmq_monitor is zmq_monitor
    assert uow._session.added_objects == [zmq_monitor]
    assert uow._session.flush_called is True
    assert uow._session.refreshed_objects == [zmq_monitor]
    assert uow.committed is False
    assert uow._session.commit_called is False



@pytest.mark.asyncio
async def test_create_zmq_monitor_with_device(device):
    uow = FakeUnitOfWork()
    expected_socket = str(AsyncPath(device.run_dir) / f"{device.service_id}-zmq-monitor.sock")

    zmq_monitor = await create_zmq_monitor(uow, device=device)

    assert zmq_monitor is not None
    assert isinstance(zmq_monitor, ZMQMonitor)
    assert zmq_monitor.transport == "ipc"
    assert zmq_monitor.socket == expected_socket
    assert zmq_monitor.device == device
    assert uow.zmq_monitors.added_zmq_monitor is zmq_monitor
    assert uow._session.added_objects == [zmq_monitor]
    assert uow._session.flush_called is True
    assert uow._session.refreshed_objects == [zmq_monitor]
    assert uow.committed is False
    assert uow._session.commit_called is False


@pytest.mark.asyncio
async def test_create_zmq_monitor_with_device_and_project(device, project):
    uow = FakeUnitOfWork()
    expected_socket = str(AsyncPath(project.run_dir) / f"{project.service_id}-zmq-monitor.sock")

    zmq_monitor = await create_zmq_monitor(uow, device=device, project=project)

    assert zmq_monitor is not None
    assert isinstance(zmq_monitor, ZMQMonitor)
    assert zmq_monitor.transport == "ipc"
    assert zmq_monitor.socket == expected_socket
    assert zmq_monitor.device == device
    assert uow.zmq_monitors.added_zmq_monitor is zmq_monitor
    assert uow._session.added_objects == [zmq_monitor]
    assert uow._session.flush_called is True
    assert uow._session.refreshed_objects == [zmq_monitor]
    assert uow.committed is False
    assert uow._session.commit_called is False


@pytest.mark.asyncio
async def test_create_zmq_monitor_without_device_or_project():
    uow = FakeUnitOfWork()

    zmq_monitor = await create_zmq_monitor(uow)

    assert zmq_monitor is not None
    assert isinstance(zmq_monitor, ZMQMonitor)
    assert zmq_monitor.transport == "ipc"
    assert zmq_monitor.device is None
    assert zmq_monitor.project is None
    assert zmq_monitor.socket is None
    assert uow.zmq_monitors.added_zmq_monitor is zmq_monitor
    assert uow._session.added_objects == [zmq_monitor]
    assert uow._session.flush_called is True
    assert uow._session.refreshed_objects == [zmq_monitor]
    assert uow.committed is False
    assert uow._session.commit_called is False
    

@pytest.mark.asyncio
async def test_create_zmq_monitor_fails(project, run_dir, mocker):

    uow = FakeUnitOfWork()
    mocker.patch.object(uow.zmq_monitors, "add", side_effect=Exception("Database is down!"))

    with pytest.raises(Exception, match="Database is down!"):
        await create_zmq_monitor(uow, project=project)

    assert uow.zmq_monitors.added_zmq_monitor is None
    assert uow._session.added_objects == []
    assert uow._session.flush_called is False
    assert uow._session.refreshed_objects == []
    assert uow.committed is False
    assert uow._session.commit_called is False

