from platform import machine
from unittest.mock import AsyncMock

import pytest
from pytest_mock import mocker
from requests import session
from svcs import Registry
from testfixtures import TempDirectory
from aiopath import AsyncPath
from uwsgiconf.runtime.scheduling import register_timer_rb

from pikesquares import services

from pikesquares.domain.device import Device
from pikesquares.service_layer.handlers.device import create_device
from pikesquares.service_layer.handlers import device
from pikesquares.service_layer.uow import UnitOfWork

# from tests.conftest import project_fixture

class FakeDeviceRepository:
    def __init__(self, existing_device: Device | None = None):
        self._device = existing_device
        self.added_device = None
        self._session = None


    async def add(self, device: Device) -> Device:
        self.added_device = device
        self._session.add(device)
        await self._session.flush()
        await self._session.refresh(device)
        return device


class FakeUoW:
    def __init__(self, device:Device | None = None):
        self.devices = FakeDeviceRepository(existing_device=device)
        self.committed = False
        self.rolled_back = False
        self._session = FakeSession()
        self.devices._session = self._session

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
        print(f"Device added: {obj}")




@pytest.mark.asyncio
async def test_create_device():
    with TempDirectory() as tmp:

        uow = FakeUoW()

        context = {
            "device": None,
            "device-zmq-monitor": None,
            "default-http-router": None,
            "default-project": None,
        }
        create_kwargs = {
            "config_dir": tmp.path,
            "data_dir": tmp.path,
            "run_dir": tmp.path,
            "log_dir": tmp.path,
        }

        device = await create_device(context, uow, "1234abc", create_kwargs)

        assert device is not None
        assert isinstance(device, Device)
        assert uow.devices.added_device.machine_id == "1234abc"
        assert uow.devices.added_device is not None
        assert uow._session.added_objects == [device]
        assert uow._session.flush_called is True


@pytest.mark.asyncio
async def test_create_device_rollback(mocker):
        uow = FakeUoW()
        context = {
            "device": None,
            "device-zmq-monitor": None,
            "default-http-router": None,
            "default-project": None,
        }

        mocker.patch.object(uow.devices, "add", new_callable=AsyncMock, side_effect=Exception("Database is down!"))


        with pytest.raises(Exception, match="Database is down!"):
            await create_device(context, uow,"1234id")


        assert uow.devices.added_device is None
        assert uow._session.added_objects == []
        assert uow._session.flush_called is False
        assert uow._session.refreshed_objects == []
        assert uow.committed is False
        assert uow._session.commit_called is False
