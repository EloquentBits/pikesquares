from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
import structlog
from asgi_lifespan import LifespanManager
from cuid import cuid
from httpx import ASGITransport, AsyncClient
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from testfixtures import TempDirectory, Replacer

from pikesquares.adapters.database import DatabaseSessionManager
from pikesquares.adapters.repositories import DeviceRepository
from pikesquares.app.main import app, lifespan
from pikesquares.conf import AppConfig, register_app_conf
from pikesquares.domain.device import Device

# from pikesquares.domain.device import Device
# from pikesquares.service_layer.uow import UnitOfWork


logger = structlog.getLogger()

pytest_plugins = ("testfixtures",)


def pytest_addoption(parser):
    parser.addoption("--configpath", action="store", help="Location to YAML file")
    parser.addoption("--env", action="store", help="Environment to read from YAML file")


@pytest.fixture()
def data_dir():
    with TempDirectory() as data_dir:
        yield data_dir


@pytest.fixture()
def config_dir():
    with TempDirectory() as config_dir:
        yield config_dir


@pytest.fixture()
def log_dir():
    with TempDirectory() as log_dir:
        yield log_dir


@pytest.fixture()
def run_dir():
    with TempDirectory() as run_dir:
        yield run_dir


@pytest.fixture(name="conf")
async def app_config_fixture(data_dir, config_dir, log_dir, run_dir):

    app_conf = AppConfig()
    r = Replacer()
    r.in_environ("PIKESQUARES_DATA_DIR", data_dir.as_string())
    r.in_environ("PIKESQUARES_CONFIG_DIR", config_dir.as_string())
    r.in_environ("PIKESQUARES_LOG_DIR", log_dir.as_string())
    r.in_environ("PIKESQUARES_RUN_DIR", run_dir.as_string())
    # r.replace("pikesquares.conf.AppConfig.data_dir", data_dir)
    # r.replace("pikesquares.conf.AppConfig.config_dir", config_dir)
    # r.replace("pikesquares.conf.AppConfig.log_dir", data_dir)
    # r.replace("pikesquares.conf.AppConfig.run_dir", run_dir)
    import ipdb

    ipdb.set_trace()
    return app_conf


def app_config_mock(conf):
    """
    AppConfig async mock
    """
    # mock.get_by_machine_id = AsyncMock(return_value=device)
    mock = Mock(from_spec=AppConfig)
    # mock.get_by_id = AsyncMock(return_value=device)
    return mock


# SESSION/DB


@pytest_asyncio.fixture(name="session")
async def session_fixture():
    sessionmanager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:", {"echo": False})
    if sessionmanager._engine:
        async with sessionmanager._engine.begin() as conn:
            await conn.run_sync(lambda conn: SQLModel.metadata.create_all(conn))

    async def get_session() -> AsyncSession:
        async with sessionmanager.session() as session:
            yield session

    session = AsyncMock(spec_set=AsyncSession)
    lifespan.registry.register_factory(AsyncSession, get_session)
    yield session


@pytest_asyncio.fixture
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(transport=ASGITransport(manager.app), base_url="http://app.io") as client:
            logger.debug("Client is ready")
            yield client


# Device
@pytest.fixture
def device():
    """
    pikesquares.domain.Device fixture
    """
    machine_id = "c8498494a94c40319a7173da7c6c9455"
    service_id = f"device_{cuid()}"
    return Device(service_id=service_id, machine_id=machine_id)


@pytest_asyncio.fixture
def device_repo_mock(device):
    """
    DeviceRepository async mock
    """
    mock = AsyncMock(from_spec=DeviceRepository)
    mock.get_by_machine_id = AsyncMock(return_value=device)
    mock.get_by_id = AsyncMock(return_value=device)
    return mock


"""
import asyncio
from contextlib import ExitStack

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

# from asyncpg import Connection
from fastapi.testclient import TestClient


# from pikesquares.conf import settings
from app.database import Base, get_db_session, sessionmanager
# from app.main import app as actual_app



@pytest.fixture(autouse=True)
def app():
    with ExitStack():
        yield actual_app


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def run_migrations(connection: Connection):
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option(
        "sqlalchemy.url",
        # settings.database_url
        "sqlite+aiosqlite:///:memory:",
    )
    script = ScriptDirectory.from_config(config)

    def upgrade(rev, context):
        return script._upgrade_revs("head", rev)

    context = MigrationContext.configure(connection, opts={"target_metadata": Base.metadata, "fn": upgrade})

    with context.begin_transaction():
        with Operations.context(context):
            context.run_migrations()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    # Run alembic migrations on test DB
    async with sessionmanager.connect() as connection:
        await connection.run_sync(run_migrations)

    yield

    # Teardown
    await sessionmanager.close()


# Each test function is a clean slate
@pytest.fixture(scope="function", autouse=True)
async def transactional_session():
    async with sessionmanager.session() as session:
        try:
            await session.begin()
            yield session
        finally:
            await session.rollback()  # Rolls back the outer transaction


@pytest.fixture(scope="function")
async def db_session(transactional_session):
    yield transactional_session


@pytest.fixture(scope="function", autouse=True)
async def session_override(app, db_session):
    async def get_db_session_override():
        yield db_session[0]

    app.dependency_overrides[get_db_session] = get_db_session_override


"""

"""
from pathlib import Path

import pytest  # type: ignore

from tinydb.middlewares import CachingMiddleware
from tinydb.storages import MemoryStorage
from tinydb import TinyDB, JSONStorage


@pytest.fixture(params=['memory', 'json'])
def db(request, tmp_path: Path):
    if request.param == 'json':
        db_ = TinyDB(tmp_path / 'test.db', storage=JSONStorage)
    else:
        db_ = TinyDB(storage=MemoryStorage)

    db_.drop_tables()
    db_.insert_multiple({'int': 1, 'char': c} for c in 'abc')

    yield db_


@pytest.fixture
def storage():
    return CachingMiddleware(MemoryStorage)()
"""
