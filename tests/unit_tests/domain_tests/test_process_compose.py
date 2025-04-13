from unittest.mock import AsyncMock, Mock, patch

from aiopath import AsyncPath
import pytest
import structlog

from pikesquares.domain.process_compose import (
    Config,
    ProcessStats,
    ProcessAvailability,
    ProcessRestart,
    Process,
    ReadinessProbeHttpGet,
    ReadinessProbe,
    ProcessMessages,
    register_process_compose,
    make_api_process,
    make_device_process,
    make_caddy_process,
    make_dnsmasq_process,
)

logger = structlog.getLogger()


@pytest.mark.asyncio
async def test_raise_exception():
    my_mock = AsyncMock(side_effect=KeyError)

    with pytest.raises(KeyError):
        await my_mock()

    my_mock.assert_called()


@pytest.mark.asyncio
async def test_register_process_compose():
    context = {}
    await register_process_compose(context)


@pytest.mark.asyncio
async def test_make_api_process(conf):
    pass


@pytest.fixture()
def device_process(device, conf, process_availability):
    cmd = f"{conf.UWSGI_BIN} --show-config --plugin {str(conf.sqlite_plugin)} --sqlite {str(conf.db_path)}:"
    sql = (
        f'"SELECT option_key,option_value FROM uwsgi_options WHERE device_id=\'{device.id}\' ORDER BY sort_order_index"'
    )
    return Process(
        description="Device Manager",
        command="".join([cmd, sql]),
        working_dir=conf.data_dir,
        availability=process_availability,
    )


@pytest.fixture()
def device_messages():
    return ProcessMessages(
        title_start="!! device start title !!",
        title_stop="!! device stop title !!",
    )


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
async def test_make_caddy_process(conf):
    pass


@pytest.mark.asyncio
async def test_make_dnsmasq_process(conf):
    pass
