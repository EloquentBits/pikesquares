from unittest.mock import Mock

import pytest

from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares.app.main import lifespan, app
from pikesquares.service_layer.uow import UnitOfWork

"""
from simple_fastapi_app import Database, app, lifespan


import os
from collections.abc import AsyncGenerator
from fastapi import FastAPI
import svcs


config = {"db_url": os.environ.get("DB_URL", "sqlite:///:memory:")}


class Database:
    @classmethod
    async def connect(cls, db_url: str) -> Database:
        # ...
        return Database()

    async def get_user(self, user_id: int) -> dict[str, str]:
        return {}  # not interesting here


@svcs.fastapi.lifespan
async def lifespan(
    app: FastAPI, registry: svcs.Registry
) -> AsyncGenerator[dict[str, object], None]:
    async def connect_to_db() -> Database:
        return await Database.connect(config["db_url"])

    registry.register_factory(Database, connect_to_db)

    yield {"your": "other stuff"}


app = FastAPI(lifespan=lifespan)


@app.get("/users/{user_id}")
async def get_user(user_id: int, services: svcs.fastapi.DepContainer) -> dict:
    db = await services.aget(Database)

    try:
        return {"data": await db.get_user(user_id)}
    except Exception as e:
        return {"oh no": e.args[0]}


@pytest.fixture(name="client")
def _client():
    with TestClient(app) as client:
        yield client

"""

######################################################
######################################################


@pytest.fixture(name="client")
def _client():
    with TestClient(app) as client:
        yield client


def test_one(client):
    """
    test one
    """
    session = Mock(spec_set=AsyncSession)
    # db.get_user.side_effect = Exception("boom")
    lifespan.registry.register_value(AsyncSession, session)

    resp = client.get("/api/v1/devices/123")

    assert {"oh no": "boom"} == resp.json()

def test_db_goes_boom(client):
    """
    Database errors are handled gracefully.
    """
    pass

    # IMPORTANT: Overwriting must happen AFTER the app is ready!
    # db = Mock(spec_set=Database)
    # db.get_user.side_effect = Exception("boom")
    # lifespan.registry.register_value(Database, db)

    # resp = client.get("/users/42")

    # assert {"oh no": "boom"} == resp.json()
