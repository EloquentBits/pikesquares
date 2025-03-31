from unittest.mock import AsyncMock

import pytest
import structlog
from sqlalchemy.sql import text

from pikesquares.adapters.repositories import DeviceRepository

logger = structlog.getLogger()


@pytest.mark.asyncio
async def test_raise_exception():
    my_mock = AsyncMock(side_effect=KeyError)

    with pytest.raises(KeyError):
        await my_mock()

    my_mock.assert_called()


@pytest.mark.asyncio
async def insert_device(session, device):
    """
    insert device raw sql
    """
    await session.exec(
        text(f"INSERT INTO device (service_id, machine_id) VALUES ('{device.service_id}', '{device.machine_id}')")
    )
    device_id = await session.exec(
        "SELECT id FROM device WHERE service_id=:service_id AND machine_id=:machine_id",
        {"service_id": device.service_id, "machine_id": device.machine_id},
    )
    # import ipdb;ipdb.set_trace()
    return device_id


@pytest.mark.asyncio
async def test_repo_can_add_a_device(session, device_repo_mock, device):
    """
    Device Repo can add a device
    """
    await device_repo_mock.add(device)
    await session.commit()
    # rows = await session.exec("SELECT service_id, machine_id FROM device")
    # session.assert_awaited()
    session.add.assert_called_once_with(device)


@pytest.mark.asyncio
async def test_repo_can_retrieve_a_device(session, device, device_repo_mock):
    # device_id = await insert_device(session, service_id, machine_id)
    insert_device_sql = (
        f"INSERT INTO device (service_id, machine_id) VALUES ('{device.service_id}', '{device.machine_id}')"
    )
    await session.exec(insert_device_sql)
    session.exec.assert_called_once_with(insert_device_sql)

    select_device_sql = (
        f"SELECT id FROM device WHERE service_id={device.service_id} AND machine_id={device.machine_id}",
    )
    device_id = await session.exec(select_device_sql)
    session.exec.assert_called_once_with(select_device_sql)

    # mock_result = AsyncMock()
    # mock_result.fetchone.return_value = {"id": 1, "name": "John Doe"}
    # mock_session.execute.return_value = mock_result

    retrieved = await device_repo_mock.get_by_machine_id(device.machine_id)
    assert device_repo_mock.get_by_machine_id.return_value == retrieved

    retrieved = await device_repo_mock.get_by_id(device_id)
    assert device_repo_mock.get_by_id.return_value == retrieved

    # mocker.patch.object(CatFact, "get_cat_fact", AsyncMock(return_value=mock_response))
    # import ipdb;ipdb.set_trace()


@pytest.mark.asyncio
async def test_repository_can_update_a_device(session, device, device_repo_mock):
    # device_id = await insert_device(session, service_id, machine_id)
    insert_device_sql = (
        f"INSERT INTO device (service_id, machine_id) VALUES ('{device.service_id}', '{device.machine_id}')"
    )
    await session.exec(insert_device_sql)

    device = await device_repo_mock.get_by_machine_id(device.machine_id)
    new_service_id = "device_cm8ol0ggm0000dhj17hhimXXX"
    new_machine_id = "C8498494a94c40319a7173da7c6c9XXX"
    device.machine_id = new_machine_id
    device.service_id = new_service_id
    await device_repo_mock.update(device)
    await session.commit()
    session.add.assert_called_once_with(device)

    retrieved = await device_repo_mock.get_by_machine_id(device.machine_id)
    assert device_repo_mock.get_by_machine_id.return_value == retrieved

    # updated_device = await device_repo_mock.get_by_id(device_id)


@pytest.mark.asyncio
async def test_repository_can_delete_a_project(session, device, device_repo_mock):
    # device_id = await insert_device(session, service_id, machine_id)
    insert_device_sql = (
        f"INSERT INTO device (service_id, machine_id) VALUES ('{device.service_id}', '{device.machine_id}')"
    )
    await session.exec(insert_device_sql)

    device = device_repo_mock.get_by_machine_id(device.machine_id)
    await device_repo_mock.delete(device)
    await session.commit()
    session.delete.assert_called_once_with(device.id)

    # deleted_device = repo.get_by_machine_id(machine_id)


"""
def test_repository_can_list_projects(db):
    insert_project(db.session, "test-project-01", "Test Project Description 1")
    insert_project(db.session, "test-project-02", "Test Project Description 2")
    insert_project(db.session, "test-project-03", "Test Project Description 3")
    
    expected = [
        Project("test-project-01", "Test Project Description 1"),
        Project("test-project-02", "Test Project Description 2"),
        Project("test-project-03", "Test Project Description 3"),
    ]
    
    repo = DeviceRepository(db.session)
    projects = repo.list_projects()
    
    for expected_project in expected:
        print(expected_project.name)
        assert any(
            project.name == expected_project.name 
            and 
            project.description == expected_project.description 
            for project in projects
        )
"""
