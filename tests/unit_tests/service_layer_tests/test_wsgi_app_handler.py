import pytest
from aiopath import AsyncPath
from pikesquares.domain.wsgi_app import WsgiApp
from pikesquares.service_layer.handlers import wsgi_app
from pikesquares.service_layer.handlers.wsgi_app import create_wsgi_app


class FakeRepository:
    def __init__(self):
        self.added_wsgi_app = None
        self._session = None

    async def add(self, wsgi_app: WsgiApp):
        self.added_wsgi_app = wsgi_app
        self._session.add(wsgi_app)
        await self._session.flush()
        await self._session.refresh(wsgi_app)


class FakeUnitOfWork:
    def __init__(self):
        self.wsgi_apps = FakeRepository()
        self.committed = False
        self._session = FakeSession()
        self.wsgi_apps._session = self._session

    async def commit(self):
        self.committed = True
        await self._session.commit()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
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
async def test_create_wsgi_app_success(project, data_dir, config_dir, run_dir, log_dir, mocker):
    uow = FakeUnitOfWork()
    runtime = mocker.Mock()
    runtime.app_root_dir = data_dir.as_path()

    pyvenv_dir = config_dir.as_path()
    wsgi_file = AsyncPath(run_dir.as_path() / "wsgi.py")

    wsgi_app = await create_wsgi_app(
        uow=uow,
        runtime=runtime,
        service_id="test-service",
        name="test_wsgi_app",
        wsgi_file=wsgi_file,
        wsgi_module="test_project.wsgi",
        project=project,
        pyvenv_dir=pyvenv_dir,
        uwsgi_plugins=["emperor_zeromq"],
    )

    assert isinstance(wsgi_app, WsgiApp)
    assert uow.wsgi_apps.added_wsgi_app == wsgi_app
    assert uow._session.added_objects == [wsgi_app]
    assert uow._session.flush_called is True
    assert uow._session.refreshed_objects == [wsgi_app]
    assert uow.committed is True
    assert uow._session.commit_called is True


@pytest.mark.asyncio
async def test_create_wsgi_app_fails(project, data_dir, config_dir, run_dir, mocker):
    uow = FakeUnitOfWork()
    mocker.patch.object(uow.wsgi_apps, "add", side_effect=Exception("Database is down!"))
    logger_mock = mocker.patch.object(wsgi_app.logger, "exception")

    runtime = mocker.Mock()
    runtime.app_root_dir = data_dir.as_path()

    pyvenv_dir = config_dir.as_path()
    wsgi_file = AsyncPath(run_dir.as_path() / "wsgi.py")

    with pytest.raises(Exception, match="Database is down!"):
        await wsgi_app.create_wsgi_app(
            uow=uow,
            runtime=runtime,
            service_id="test-service",
            name="test_wsgi_app",
            wsgi_file=wsgi_file,
            wsgi_module="test_project.wsgi",
            project=project,
            pyvenv_dir=pyvenv_dir,
            uwsgi_plugins=["emperor_zeromq"],
        )

    assert "Database is down!" in str(logger_mock.call_args[0][0])
    assert uow.wsgi_apps.added_wsgi_app is None
    assert uow._session.added_objects == []
    assert uow._session.flush_called is False
    assert uow._session.refreshed_objects == []
    assert uow.committed is False
    assert uow._session.commit_called is False
