from unittest.mock import AsyncMock


import structlog
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
# from fastapi.testclient import TestClient
 #from sqlmodel.pool import StaticPool
from sqlmodel import (
    # Session,
    SQLModel,
    # create_engine,
)
from sqlmodel.ext.asyncio.session import AsyncSession
from asgi_lifespan import LifespanManager


from .main import app, lifespan
from pikesquares.domain.device import Device
from pikesquares.adapters.database import DatabaseSessionManager
from pikesquares.service_layer.uow import UnitOfWork


logger = structlog.getLogger()

"""
@pytest.fixture(name="session")
async def session_fixture():
    # engine = create_engine(
    #    "sqlite://",
    #    connect_args={"check_same_thread": False},
    #    poolclass=StaticPool,
    # )

    sessionmanager = DatabaseSessionManager(
    "sqlite:///:memory:", {"echo": True}
    )

    if sessionmanager._engine:
        async with sessionmanager._engine.begin() as conn:
            await conn.run_sync(
                lambda conn: SQLModel.metadata.create_all(conn)
            )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

"""


@pytest_asyncio.fixture(name="session")
async def session_fixture():
    sessionmanager = DatabaseSessionManager(
        "sqlite+aiosqlite:///:memory:", {"echo": False}
    )
    if sessionmanager._engine:
        async with sessionmanager._engine.begin() as conn:
            await conn.run_sync(
                lambda conn: SQLModel.metadata.create_all(conn)
            )

    async def get_session() -> AsyncSession:
        async with sessionmanager.session() as session:
            yield session

    session = AsyncMock(spec_set=AsyncSession)
    lifespan.registry.register_factory(AsyncSession, get_session)
    yield session


@pytest_asyncio.fixture
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
                transport=ASGITransport(manager.app),
                base_url="http://app.io"
            ) as client:
            logger.debug("Client is ready")
            yield client


@pytest.mark.asyncio
async def test_healthy(client):

    response = await client.get("/healthy")
    assert response.status_code == 200
    # assert response.json() == {"message": "Tomato"}


machine_id = "c8498494a94c40319a7173da7c6c9455"
service_id = "device_cm8ol0ggm0000dhj17hhim1rh"


@pytest.mark.asyncio
async def test_add_device(
    session: AsyncSession,
    # client: AsyncClient,
    ):
    """
    DB Add device
    """
    async with UnitOfWork(session=session) as uow:
        device = Device(service_id=service_id, machine_id=machine_id)
        await uow.devices.add(device)
        await uow.commit()

    # response = await client.get(f"/api/v1/devices/{machine_id}")
    # assert response.status_code == 200


@pytest.mark.asyncio
async def test_read_device(client):
    """
    API GET device
    """
    response = await client.get(f"/api/v1/devices/{machine_id}")
    assert response.status_code == 200

    response = await client.get("/api/v1/devices/123")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_by_machine_id(session: AsyncSession):
    """
    DB GET device
    """
    async with UnitOfWork(session=session) as uow:
        device = await uow.devices.get_by_machine_id(machine_id)
        assert device.machine_id == machine_id
        assert device.service_id == service_id
