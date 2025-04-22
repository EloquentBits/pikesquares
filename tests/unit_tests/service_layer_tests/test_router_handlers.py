import pytest
import pytest_asyncio
from cuid import cuid
from testfixtures import TempDirectory
from aiopath import AsyncPath
from pikesquares import get_first_available_port
#from pikesquares.app.api.routes.services.devices import router
#from pikesquares.app.api.routes.services.routers import add_router
#from pikesquares.domain.device import Device
from pikesquares.domain.router import BaseRouter
from pikesquares.service_layer.handlers.routers import get_or_create_http_router
from pikesquares.service_layer.uow import UnitOfWork
from tests.conftest import device


class FakeRepository:
    def __init__(self, existing_router: BaseRouter | None = None):
        self._router = existing_router
        self.added_router = None

    async def get_by_name(self, name:str) -> BaseRouter | None:
        return self._router

    async def add(self, router: BaseRouter):
        self.added_router = router


class FakeUoW:
    def __init__(self, router: BaseRouter | None = None):
        self.routers = FakeRepository(existing_router=router)
        self.committed = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


#@pytest_asyncio.fixture
#async def fake_device():
    # return Device(
    #     service_id="device_333",
    #     machine_id="machine_abc",
    #     config_dir="/tmp/fake_config",
    #     data_dir="/tmp/fake_data",
    #     run_dir="/tmp/fake_run",
    #     log_dir="/tmp/fake_log",
    # )


@pytest.mark.asyncio
async def test_creates_router(device):
    with TempDirectory() as tmp:
        uow = FakeUoW()
        create_kwargs = {
                "config_dir": tmp.path,
                "data_dir": tmp.path,
                "run_dir": tmp.path,
                "log_dir": tmp.path,
            }

        router = await get_or_create_http_router("sandbox", device, uow, create_kwargs)

        assert uow.committed
        assert uow.routers.added_router.name == "sandbox"
        assert uow.routers.added_router is not None

# Device
# @pytest.fixture
# def BaseRouter():
#     machine_id = "c82398494a94c40319a337173da7c6c934455"
#     service_id = f"device_{cuid()}"
#     return BaseRouter(service_id=service_id, machine_id=machine_id)


@pytest.mark.asyncio
async def test_get_router(device, fix_router):
    with TempDirectory() as tmp:
        uow = FakeUoW(router=fix_router)
        create_kwargs = {
            "config_dir": tmp.path,
            "data_dir": tmp.path,
            "run_dir": tmp.path,
            "log_dir": tmp.path,
        }

    router = await get_or_create_http_router("sandbox", device, uow, create_kwargs)

    assert router is fix_router
    assert uow.routers.added_router is None
    assert uow.committed is False


# Negative
@pytest.mark.asyncio
async def test_none_uow(device):
    with TempDirectory() as tmp:
        create_kwargs = {
            "config_dir": tmp.path,
            "data_dir": tmp.path,
            "run_dir": tmp.path,
            "log_dir": tmp.path,
        }

        with pytest.raises(AttributeError):
            await get_or_create_http_router("sandbox", device, "None", create_kwargs)

