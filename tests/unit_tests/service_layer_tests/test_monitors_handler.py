import pytest
from aiopath import AsyncPath
from pikesquares.service_layer.handlers import monitors # for logger
from pikesquares.domain.monitors import ZMQMonitor
from pikesquares.service_layer.handlers.monitors import create_zmq_monitor

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
async def test_create_zmq_monitor(project, run_dir):

    uow = FakeUnitOfWork()
    expected_socket = str(AsyncPath(run_dir.path) / f"{project.service_id}-zmq-monitor.sock")

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
    assert uow.committed is True
    assert uow._session.commit_called is True


@pytest.mark.asyncio
async def test_create_zmq_monitor_rollback(project, run_dir, mocker):

    uow = FakeUnitOfWork()
    mocker.patch.object(uow.zmq_monitors, "add", side_effect=Exception("Database is down!"))
    logger_mock = mocker.patch.object(monitors.logger, "exception")

    with pytest.raises(Exception, match="Database is down!"):
        await create_zmq_monitor(uow, project=project)

    assert "Database is down!" in str(logger_mock.call_args[0][0])
    assert uow.zmq_monitors.added_zmq_monitor is None
    assert uow._session.added_objects == []
    assert uow._session.flush_called is False
    assert uow._session.refreshed_objects == []
    assert uow.committed is False
    assert uow._session.commit_called is False
