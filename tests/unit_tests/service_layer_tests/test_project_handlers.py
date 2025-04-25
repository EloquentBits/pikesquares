import pytest
from pikesquares.domain.project import Project
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.service_layer.handlers import project as pk_project  # for logger
from pikesquares.service_layer.handlers.project import create_project

class FakeRepository:
    def __init__(self, existing_project: Project | None = None):
        self._project = existing_project
        self.added_project = None
        self._session = None

    async def get_by_name(self, name: str) -> Project | None:
        return self._project

    async def add(self, project: Project):
        self.added_project = project
        self._session.add(project)
        await self._session.flush()
        await self._session.refresh(project)


class FakeUnitOfWork:
    def __init__(self, project: Project | None = None):
        self.projects = FakeRepository(existing_project=project)
        self.zmq_monitors = None
        self.committed = False
        self.rolled_back = False
        self._session = FakeSession()
        self.projects._session = self._session

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

@pytest.mark.asyncio
async def test_create_project(zmq_monitor_repo_mock, registry, context, mocker):

    uow = FakeUnitOfWork()
    zmq_monitor_repo_mock.get_by_device_id.return_value = None
    zmq_monitor_repo_mock.get_by_project_id.return_value = None
    zmq_monitor_repo_mock.add = mocker.AsyncMock()
    uow.zmq_monitors = zmq_monitor_repo_mock
    registry.register_factory(UnitOfWork, lambda: uow)
    device = context.get("device")

    project = await create_project("sandbox", context, uow)

    assert project is not None
    assert isinstance(project, Project)
    assert project.device == device
    assert project.data_dir == str(device.data_dir)
    assert project.config_dir == str(device.config_dir)
    assert project.run_dir == str(device.run_dir)
    assert project.log_dir == str(device.log_dir)
    assert project.uwsgi_plugins == "emperor_zeromq"
    assert uow.projects.added_project is project
    assert uow._session.added_objects == [project]
    assert uow._session.flush_called is True
    assert uow._session.refreshed_objects == [project]
    assert uow.committed is True
    assert uow._session.commit_called is True
    

@pytest.mark.asyncio
async def test_add_project_rollbacks(registry, context, mocker):

    uow = FakeUnitOfWork()
    mocker.patch.object(uow.projects, "add", side_effect=Exception("Database is down!"))
    mocker.patch.object(pk_project.logger, "exception", return_value=None)
    registry.register_factory(UnitOfWork, lambda: uow)

    project = await create_project("sandbox", context, uow)

    # assert project is None
    assert uow.projects.added_project is None
    assert uow._session.added_objects == []
    assert uow._session.flush_called is False
    assert uow._session.refreshed_objects == []
    assert uow.committed is False
    assert uow._session.commit_called is False
    assert uow.rolled_back is True