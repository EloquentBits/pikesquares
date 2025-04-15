from unittest import mock
import json

import pytest
import structlog

# from aiopath import AsyncPath
from pikesquares.conf import AppConfig
from pikesquares.domain import process_compose
from pikesquares.domain.device import Device
from pikesquares.domain.process_compose import (
    Config,
    Process,
    ProcessAvailability,
    ProcessMessages,
    ProcessRestart,
    ProcessStats,
    ReadinessProbe,
    ReadinessProbeHttpGet,
    make_api_process,
    make_device_process,
    make_dnsmasq_process,
    register_process_compose,
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