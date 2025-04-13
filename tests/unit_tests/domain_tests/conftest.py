from unittest.mock import Mock

import structlog
import pytest


from pikesquares.domain.process_compose import (
    Config,
    ProcessStats,
    ProcessAvailability,
    ProcessRestart,
    Process,
    ReadinessProbeHttpGet,
    ReadinessProbe,
    ProcessMessages,
)

logger = structlog.getLogger()


@pytest.fixture(name="process_availability")
async def process_availability_fixture():
    process_availability = ProcessAvailability()
    return process_availability


def process_compose_config_mock():
    """
    Config mock
    """
    # mock.get_by_machine_id = AsyncMock(return_value=device)

    mock = Mock(from_spec=Config)
    mock.processes = Mock()
    mock.custom_messages = Mock()

    api_process_messages = ProcessMessages(
        title_start="!! api start title !!!",
        title_stop="abc",
    )
    api_port = 9544
    # cmd = f"{conf.UV_BIN} run fastapi dev --port {api_port} src/pikesquares/app/main.py"
    cmd = f"{conf.UV_BIN} run uvicorn pikesquares.app.main:app --host 0.0.0.0 --port {api_port}"

    api_process = Process(
        description="PikeSquares API",
        command=cmd,
        working_dir=Path().cwd(),
        availability=ProcessAvailability(),
        readiness_probe=ReadinessProbe(http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)),
    )

    # mock.get_by_id = AsyncMock(return_value=device)
    return mock
