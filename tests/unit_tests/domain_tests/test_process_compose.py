import json
from subprocess import PIPE
from unittest import mock

import pytest
import structlog
from testfixtures import (
    Replacer,
    ShouldRaise,
    compare,
)
from testfixtures.mock import call
from testfixtures.popen import MockPopen

# from aiopath import AsyncPath
from pikesquares.conf import AppConfig
from pikesquares.domain import process_compose
from pikesquares.domain.device import Device
from pikesquares.domain.process_compose import (
    Process,
    ProcessMessages,
    # ProcessRestart,
    # ProcessStats,
    # ReadinessProbe,
    # ReadinessProbeHttpGet,
    # make_api_process,
    make_device_process,
    # make_dnsmasq_process,
    register_process_compose, make_dnsmasq_process,
)

logger = structlog.getLogger()


@pytest.mark.asyncio
async def test_raise_exception():
    my_mock = mock.AsyncMock(side_effect=KeyError)

    with pytest.raises(KeyError):
        await my_mock()

    my_mock.assert_called()


@pytest.mark.asyncio
async def test_register_process_compose(
    conf: AppConfig,
    device: Device,
    device_process: Process,
    device_messages: ProcessMessages,
):
    context = {}
    await register_process_compose(context)


@pytest.mark.asyncio
async def test_make_api_process(conf):
    pass


@pytest.mark.asyncio
async def test_make_device_process(conf, device, device_process, device_messages):
    # with patch.object(AsyncPath, 'exists') as mock_exists:
    #    mock_exists.return_value = True
    #    .exists()
    process, messages = await make_device_process(device, conf)

    assert device_messages.title_start == messages.title_start
    assert device_messages.title_stop == messages.title_stop
    assert device_process.description == process.description
    assert device_process.command == process.command


@pytest.mark.asyncio
async def test_make_caddy_process(
    conf: AppConfig,
    caddy_config: str,
    caddy_process: Process,
    caddy_messages: ProcessMessages,
):
    with (
        mock.patch("pikesquares.domain.process_compose.json.dump") as _json_dump,
        mock.patch("pikesquares.domain.process_compose.open", mock.mock_open()) as _open,
    ):
        new_process, new_messages = await process_compose.make_caddy_process(conf, http_router_port=8034)

        _open.assert_called_with(conf.caddy_config_path, "r+")
        _json_dump.assert_called_once_with(json.loads(caddy_config), _open())

    assert caddy_process.command == new_process.command
    assert caddy_messages.title_start == new_messages.title_start
    assert caddy_messages.title_stop == new_messages.title_stop


@pytest.mark.asyncio
async def test_make_dnsmasq_process(conf, dnsmasq_process, dnsmasq_messages):
    process, messages = await make_dnsmasq_process(conf, port=5353, listen_address= "127.0.0.34")

    assert dnsmasq_messages.title_start == messages.title_start
    assert dnsmasq_messages.title_stop == messages.title_stop
    assert dnsmasq_process.description == process.description
    assert dnsmasq_process.command == process.command

@pytest.mark.asyncio
async def test_process_compose_config(config_fixture):
    assert len(config_fixture.processes) == 4
    assert len(config_fixture.custom_messages) == 4


@pytest.mark.asyncio
async def test_process_compose(config_fixture, process_compose_fixture):
    assert process_compose_fixture.config == config_fixture


@pytest.mark.asyncio
async def test_process_compose_up(process_compose_fixture, run_dir, config_dir, log_dir, data_dir):
    daemon_config = config_dir / "process-compose.yaml"
    daemon_log = log_dir / "process-compose.log"
    daemon_socket = run_dir / "process-compose.sock"
    pc_up_cmd = [
        "up",
        "--config",
        # str(process_compose_fixture.daemon_config),
        str(daemon_config),
        "--log-file",
        # str(process_compose_fixture.daemon_log),
        str(daemon_log),
        "--detached",
        "--hide-disabled",
        "--unix-socket",
        # str(process_compose_fixture.daemon_socket),
        str(daemon_socket),
    ]
    m_popen = MockPopen()
    r = Replacer()
    r.replace("plumbum.commands.base.Popen", m_popen)
    m_popen.set_command("".join(pc_up_cmd), stdout=b"o", stderr=b"e")

    # import ipdb
    # ipdb.set_trace()
    compare(await process_compose_fixture.up(), b"o")

    process = call.Popen(pc_up_cmd, stderr=PIPE, stdout=PIPE)
    compare(m_popen.all_calls, expected=[process, process.communicate()])

    r.restore()
