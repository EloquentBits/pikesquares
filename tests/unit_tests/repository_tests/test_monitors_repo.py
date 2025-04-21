import uuid
import pytest
from aiopath import AsyncPath
import pytest_asyncio
import structlog
from testfixtures import TempDirectory
from sqlalchemy.sql import text

# from pikesquares.adapters.repositories import DeviceRepository
#
logger = structlog.getLogger()


@pytest.mark.asyncio
async def test_repo_can_add_a_monitor(session, zmq_monitor_repo_mock, device_zmq_monitor, device):
    """
    ZMQMonitor Repo can add a zmq monitor
    """

    new_monitor = await zmq_monitor_repo_mock.add(device_zmq_monitor)
    await session.commit()
    assert new_monitor.id == device_zmq_monitor.id
    assert new_monitor.device.id == device.id
    assert new_monitor.device == device
    assert new_monitor.socket == device_zmq_monitor.socket


@pytest.mark.asyncio
async def test_repo_can_get_a_monitor(session, zmq_monitor_repo_mock, device_zmq_monitor, device):
    """
    ZMQMonitor Repo can get a zmq monitor
    """

    new_monitor = await zmq_monitor_repo_mock.add(device_zmq_monitor)
    await session.commit()

    get_new_monitor = await zmq_monitor_repo_mock.get_by_id(device_zmq_monitor.id)
    assert new_monitor.id == get_new_monitor.id
    assert new_monitor.device.id == device.id
    assert new_monitor.device == device
    assert new_monitor.socket == get_new_monitor.socket
