import pytest
from svcs import Registry
from pikesquares.domain.project import Project

@pytest.fixture
def registry():
    return Registry()

@pytest.fixture
def context(device, registry):
    return {"device": device, "svcs_registry": registry}

@pytest.fixture
def create_kwargs(data_dir, config_dir, run_dir, log_dir):
    return {
        "data_dir": data_dir.as_path(),
        "config_dir": config_dir.as_path(),
        "run_dir": run_dir.as_path(),
        "log_dir": log_dir.as_path(),
    }
    
@pytest.fixture
def project(device, data_dir, config_dir, run_dir, log_dir):
    return Project(
        service_id="test-service",
        name="test-project",
        device=device,
        data_dir=data_dir.as_path(),
        config_dir=config_dir.as_path(),
        run_dir=run_dir.as_path(),
        log_dir=log_dir.as_path(),
        uwsgi_plugins="emperor_zeromq",
    )