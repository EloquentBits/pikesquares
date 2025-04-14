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


@pytest.fixture()
async def process_availability():
    process_availability = ProcessAvailability()
    return process_availability


@pytest.fixture
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


@pytest.fixture
def api_messages():
    return ProcessMessages(
        title_start="!! api start title !!",
        title_stop="!! api stop title !!",
    )


@pytest.fixture
def api_process(device, conf, process_availability): ...


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
    caddy_config_file = conf.config_dir / "caddy.json"
    return Process(
        description="reverse proxy",
        command=f"{conf.CADDY_BIN} run --config {caddy_config_file} --pidfile {conf.run_dir / 'caddy.pid'}",
        working_dir=conf.data_dir,
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
    cmd = f"{conf.DNSMASQ_BIN} --keep-in-foreground --port {port} --listen-address {listen_address} --no-resolv"
    cmd = cmd + " --address /pikesquares.local/192.168.0.1"
    return Process(
        description="dns resolver",
        command=cmd,
        working_dir=conf.data_dir,
        availability=process_availability,
        # readiness_probe=ReadinessProbe(
        #    http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
        # ),
    )


@pytest.fixture
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
