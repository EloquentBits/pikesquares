import os.path
import pytest
import pytest_asyncio
from testfixtures import TempDirectory
from pikesquares.domain.device import Device
from pikesquares.domain.project import Project
from pikesquares.service_layer.handlers.project import get_or_create_project


class FakeRepository:
    def __init__(self, existing_project: Project | None = None):
        self._project = existing_project
        self.added_project = None

    async def get_by_name(self, name: str) -> Project | None:
        return self._project

    async def add(self, project: Project):
        self.added_project = project


class FakeUoW:
    def __init__(self, project: Project | None = None):
        self.projects = FakeRepository(existing_project=project)
        self.committed = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


@pytest_asyncio.fixture
async def fake_device():
    return Device(
        service_id="device_123",
        machine_id="machine_abc",
        config_dir="/tmp/fake_config",
        data_dir="/tmp/fake_data",
        run_dir="/tmp/fake_run",
        log_dir="/tmp/fake_log",
    )

# Positive
@pytest.mark.asyncio
async def test_creates_project(fake_device):
    with TempDirectory() as tmp:
        uow = FakeUoW()
        create_kwargs = {
            "config_dir": tmp.path,
            "data_dir": tmp.path,
            "run_dir": tmp.path,
            "log_dir": tmp.path,
        }

        project = await get_or_create_project("sandbox", fake_device, uow, create_kwargs)

        assert uow.committed
        assert project.name == "sandbox"
        assert uow.projects.added_project is not None
        assert uow.projects.added_project.name == "sandbox"
        assert os.path.exists(project.config_dir)  
        

@pytest.mark.asyncio
async def test_get_project(fake_device):
    existing = Project(
        service_id="project_456",
        name="sandbox",
        device=fake_device,
        config_dir="/tmp/existing_config",
        data_dir="/tmp/existing_data",
        run_dir="/tmp/existing_run",
        log_dir="/tmp/existing_log",
    )

    uow = FakeUoW(project=existing)
    project = await get_or_create_project("sandbox", fake_device, uow, create_kwargs={})

    assert project is existing
    assert uow.projects.added_project is None
    assert uow.committed is False

# Negative
@pytest.mark.asyncio
async def test_none_uow(fake_device):
    with TempDirectory() as tmp:
        create_kwargs = {
            "config_dir": tmp.path,
            "data_dir": tmp.path,
            "run_dir": tmp.path,
            "log_dir": tmp.path,
        }

        with pytest.raises(AttributeError):
            await get_or_create_project("sandbox", fake_device, None, create_kwargs)
            
