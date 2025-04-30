import pytest
from pikesquares.domain.project import Project
from pikesquares.service_layer.handlers import project
from pikesquares.service_layer.handlers.project import create_project

class FakeRepository:
    def __init__(self, existing_project: Project | None = None):
        self._project = existing_project
        self.added_project = None
        self._session = None

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
async def test_create_project_success(zmq_monitor_repo_mock, registry, context, mocker):

    uow = FakeUnitOfWork()
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
async def test_create_project_fails(registry, context, mocker):

    uow = FakeUnitOfWork()
    mocker.patch.object(uow.projects, "add", side_effect=Exception("Database is down!"))
    logger_mock = mocker.patch.object(project.logger, "exception")


    with pytest.raises(Exception, match="Database is down!"):
        await create_project("sandbox", context, uow)

    assert "Database is down!" in str(logger_mock.call_args[0][0])
    assert uow.projects.added_project is None
    assert uow._session.added_objects == []
    assert uow._session.flush_called is False
    assert uow._session.refreshed_objects == []
    assert uow.committed is False
    assert uow._session.commit_called is False
