import pytest
import pytest_asyncio
from cuid import cuid
from testfixtures import TempDirectory
from aiopath import AsyncPath
from pikesquares import get_first_available_port
from pikesquares.domain.device import Device
#from pikesquares.app.api.routes.services.devices import router
#from pikesquares.app.api.routes.services.routers import add_router
#from pikesquares.domain.device import Device
from pikesquares.domain.router import BaseRouter
from pikesquares.service_layer.handlers.routers import create_http_router

from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.services.router import HttpsRouter


class FakeRouterRepository:
    def __init__(self, existing_router: HttpsRouter | None = None):
        self._router = existing_router
        self.added_router = None
        self._session = None


    async def add(self, router: HttpsRouter) -> HttpsRouter:
        self.added_router = router
        self._session.add(router)
        await self._session.flush()
        await self._session.refresh(router)
        return router


class FakeUoW:
    def __init__(self, router: HttpsRouter | None = None):
        self.routers = FakeRouterRepository(existing_router=router)
        self.committed = False
        self.rolled_back = False
        self._session = FakeSession()
        self.routers._session = self._session

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
        print(f"Router added: {obj}")




@pytest.mark.asyncio
async def test_creates_router(device):
    uow = FakeUoW()
    context = {
        "device": device,
        "device-zmq-monitor": None,
        "default-http-router": None,
        "default-project": None,
    }

    router = await create_http_router("sandbox", context, uow)

    assert router is not None
    assert uow.routers.added_router is not None
    assert uow.routers.added_router.name == "sandbox"
    assert uow._session.added_objects == [router]
    assert uow._session.flush_called is True

# Device
# @pytest.fixture
# def BaseRouter():
#     machine_id = "c82398494a94c40319a337173da7c6c934455"
#     service_id = f"device_{cuid()}"
#     return BaseRouter(service_id=service_id, machine_id=machine_id)

#
#
#
# # Negative
# @pytest.mark.asyncio
# async def test_none_uow(device):
#     with TempDirectory() as tmp:
#         create_kwargs = {
#             "config_dir": tmp.path,
#             "data_dir": tmp.path,
#             "run_dir": tmp.path,
#             "log_dir": tmp.path,
#         }
#
#         with pytest.raises(AttributeError):
#             await get_or_create_http_router("sandbox", device, "None", create_kwargs)
#

@pytest.mark.asyncio
async def test_create_router_rollback(mocker, device):

    uow = FakeUoW()
    context = {
        "device": device,
        "device-zmq-monitor": None,
        "default-http-router": None,
        "default-project": None,
    }

    mocker.patch.object(uow.routers, "add", side_effect=Exception("Database is down!"))

    with pytest.raises(Exception, match="Database is down!"):
        await create_http_router("sandbox", context, uow)


    assert uow.routers.added_router is None
    assert uow._session.added_objects == []
    assert uow._session.flush_called is False
    assert uow._session.refreshed_objects == []
    assert uow.committed is False
    assert uow._session.commit_called is False
