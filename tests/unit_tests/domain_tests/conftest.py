from unittest.mock import Mock
from pathlib import Path

import structlog
import pytest

from testfixtures import TempDirectory

from pikesquares.domain.process_compose import (
    ProcessCompose,
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


@pytest.fixture()
async def process_availability():
    return ProcessAvailability()


@pytest.fixture
def device_process(device, conf, process_availability):
    sqlite_plugin = Path("/var/lib/pikesquares/plugins/sqlite3_plugin.so")
    db_path = Path("/var/lib/pikesquares/pikesquares.db")
    cmd = f"{conf.UWSGI_BIN} --show-config --plugin {str(sqlite_plugin)} --sqlite {str(db_path)}:"
    sql = (
        f'"SELECT option_key,option_value FROM uwsgi_options WHERE device_id=\'{device.id}\' ORDER BY sort_order_index"'
    )
    with TempDirectory() as data_dir:
        return Process(
            description="Device Manager",
            command="".join([cmd, sql]),
            working_dir=data_dir.as_path(),
            availability=process_availability,
        )


@pytest.fixture
def device_messages():
    return ProcessMessages(
        title_start="!! device start title !!",
        title_stop="!! device stop title !!",
    )


@pytest.fixture
def api_messages():
    return ProcessMessages(
        title_start="!! api start title !!",
        title_stop="!! api stop title !!",
    )


@pytest.fixture
def api_process(conf, process_availability):
    api_port = 9544
    cmd = f"{conf.UV_BIN} run uvicorn pikesquares.app.main:app --host 0.0.0.0 --port {api_port}"
    with TempDirectory() as data_dir:
        return Process(
            description="PikeSquares API",
            command=cmd,
            working_dir=data_dir.as_path(),
            availability=process_availability,
            readiness_probe=ReadinessProbe(http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)),
        )


@pytest.fixture
def caddy_messages():
    return ProcessMessages(
        title_start="!! caddy start title !!",
        title_stop="!! caddy stop title !!",
    )


@pytest.fixture
def caddy_config():
    return """\
{
  "apps": {
    "http": {
      "https_port": 443,
      "servers": {
        "*.pikesquares.local": {
          "listen": [
            ":443"
          ],
          "routes": [
            {
              "match": [
                {
                  "host": [
                    "*.pikesquares.local"
                  ]
                }
              ],
              "handle": [
                {
                  "handler": "reverse_proxy",
                  "transport": {
                    "protocol": "http"
                  },
                  "upstreams": [
                    {
                      "dial": "127.0.0.1:8034"
                    }
                  ]
                }
              ]
            }
          ]
        }
      }
    },
    "tls": {
      "automation": {
        "policies": [
          {
            "issuers": [
              {
                "module": "internal"
              }
            ]
          }
        ]
      }
    }
  },
  "storage": {
    "module": "file_system",
    "root": "/var/lib/pikesquares/caddy"
  }
}"""


@pytest.fixture
def caddy_config_default():
    return """{"apps": {"http": {"https_port": 443, "servers": {"*.pikesquares.local": {"listen": [":443"], "routes": [{"match": [{"host": ["*.pikesquares.local"]}], "handle": [{"handler": "reverse_proxy", "transport": {"protocol": "http"}, "upstreams": [{"dial": "127.0.0.1:8035"}]}]}]}}}, "tls": {"automation": {"policies": [{"issuers": [{"module": "internal"}]}]}}}, "storage": {"module": "file_system", "root": "/var/lib/pikesquares/caddy"}}"""


@pytest.fixture
def caddy_process(conf, process_availability):
    with TempDirectory() as data_dir, TempDirectory() as config_dir, TempDirectory() as run_dir:
        return Process(
            description="reverse proxy",
            command=f"{conf.CADDY_BIN} run --config {config_dir / "caddy.json" } --pidfile {run_dir.as_path() / "caddy.pid" }",
            working_dir=data_dir.as_path(),
            availability=process_availability,
            # readiness_probe=ReadinessProbe(
            #    http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
            # ),
        )


@pytest.fixture
def dnsmasq_messages():
    return ProcessMessages(
        title_start="!! dnsmasq start title !!",
        title_stop="!! dnsmasq stop title !!",
    )


@pytest.fixture
def dnsmasq_process(conf, process_availability):
    port = 8034
    listen_address = "127.0.0.34"
    cmd = f"{conf.DNSMASQ_BIN} --keep-in-foreground --port {port} --listen-address {listen_address} --no-resolv"
    cmd = cmd + " --address /pikesquares.local/192.168.0.1"

    with TempDirectory() as data_dir:

        return Process(
            description="dns resolver",
            command=cmd,
            working_dir=data_dir.as_path(),
            availability=process_availability,
            # readiness_probe=ReadinessProbe(
            #    http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
            # ),
        )


@pytest.fixture(name="config_fixture")
def config(
    device_messages,
    device_process,
    api_messages,
    api_process,
    caddy_messages,
    caddy_process,
    dnsmasq_messages,
    dnsmasq_process,
):
    return Config(
        processes={
            "api": api_process,
            "device": device_process,
            "caddy": caddy_process,
            "dnsmasq": dnsmasq_process,
        },
        custom_messages={
            "api": api_messages,
            "device": device_messages,
            "caddy": caddy_messages,
            "dnsmasq": dnsmasq_messages,
        },
    )


def process_compose_config_mock(conf, data_dir):
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
        working_dir=data_dir.as_path(),
        availability=ProcessAvailability(),
        readiness_probe=ReadinessProbe(http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)),
    )

    # mock.get_by_id = AsyncMock(return_value=device)
    return mock


@pytest.fixture()
def pc_log_dir():
    with TempDirectory(create=True) as log_dir:
        yield log_dir


@pytest.fixture()
def pc_data_dir():
    with TempDirectory(create=True) as data_dir:
        yield data_dir


@pytest.fixture()
def pc_config_dir():
    with TempDirectory(create=True) as config_dir:
        yield config_dir


@pytest.fixture()
def pc_run_dir():
    with TempDirectory(create=True) as config_dir:
        yield config_dir


@pytest.fixture(name="pc")
def process_compose(conf, config_fixture, pc_log_dir, pc_config_dir, pc_run_dir, pc_data_dir):

    daemon_config = pc_config_dir.as_path() / "process-compose.yaml"
    daemon_config.touch()

    daemon_log = pc_log_dir.as_path() / "process-compose.log"
    daemon_log.touch()

    pc_kwargs = {
        "config": config_fixture,
        "daemon_name": "process-compose",
        "daemon_bin": conf.PROCESS_COMPOSE_BIN,
        "daemon_config": daemon_config,
        "daemon_log": daemon_log,
        "daemon_socket": pc_run_dir.as_path() / "process-compose.sock",
        "data_dir": pc_data_dir.as_path(),
        "uv_bin": conf.UV_BIN,
    }
    return ProcessCompose(**pc_kwargs)
