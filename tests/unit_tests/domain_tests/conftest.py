from unittest.mock import Mock

import structlog
import pytest

from polyfactory.factories.pydantic_factory import ModelFactory

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


class ProcessComposeFactory(ModelFactory[ProcessCompose]): ...


class ConfigFactory(ModelFactory[Config]): ...


class ProcessAvailabilityFactory(ModelFactory[ProcessAvailability]): ...


class ProcessStatsFactory(ModelFactory[ProcessStats]): ...


class ProcessFactory(ModelFactory[Process]): ...


class ProcessMessagesFactory(ModelFactory[ProcessMessages]): ...


class ReadinessProbeFactory(ModelFactory[ReadinessProbe]): ...


@pytest.fixture()
async def process_availability():
    process_availability = ProcessAvailabilityFactory.build(
        factory_use_construct=True,
    )
    return process_availability


@pytest.fixture
def device_process(device, conf, process_availability):
    cmd = f"{conf.UWSGI_BIN} --show-config --plugin {str(conf.sqlite_plugin)} --sqlite {str(conf.db_path)}:"
    sql = (
        f'"SELECT option_key,option_value FROM uwsgi_options WHERE device_id=\'{device.id}\' ORDER BY sort_order_index"'
    )
    return ProcessFactory.build(
        factory_use_construct=True,
        description="Device Manager",
        command="".join([cmd, sql]),
        working_dir=conf.data_dir,
        availability=process_availability,
    )


@pytest.fixture
def device_messages():
    return ProcessMessagesFactory.build(
        factory_use_construct=True,
        title_start="!! device start title !!",
        title_stop="!! device stop title !!",
    )


@pytest.fixture
def api_messages():
    return ProcessMessagesFactory.build(
        factory_use_construct=True,
        title_start="!! api start title !!",
        title_stop="!! api stop title !!",
    )


@pytest.fixture
def api_process(conf, process_availability):
    api_port = 9544
    cmd = f"{conf.UV_BIN} run uvicorn pikesquares.app.main:app --host 0.0.0.0 --port {api_port}"
    return ProcessFactory.build(
        factory_use_construct=True,
        description="PikeSquares API",
        command=cmd,
        working_dir=conf.data_dir,
        availability=process_availability,
        readiness_probe=ReadinessProbeFactory.build(
            factory_use_construct=True, http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
        ),
    )


@pytest.fixture
def caddy_messages():
    return ProcessMessagesFactory.build(
        factory_use_construct=True,
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
    return ProcessFactory.build(
        factory_use_construct=True,
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
    return ProcessMessagesFactory.build(
        factory_use_construct=True,
        title_start="!! dnsmasq start title !!",
        title_stop="!! dnsmasq stop title !!",
    )


@pytest.fixture
def dnsmasq_process(conf, process_availability):
    port = 8034
    listen_address = "127.0.0.34"
    cmd = f"{conf.DNSMASQ_BIN} --keep-in-foreground --port {port} --listen-address {listen_address} --no-resolv"
    cmd = cmd + " --address /pikesquares.local/192.168.0.1"
    return ProcessFactory.build(
        factory_use_construct=True,
        description="dns resolver",
        command=cmd,
        working_dir=conf.data_dir,
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
    return ConfigFactory.build(
        factory_use_construct=True,
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


def process_compose_config_mock(conf):
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
        working_dir=conf.data_dir,
        availability=ProcessAvailability(),
        readiness_probe=ReadinessProbe(http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)),
    )

    # mock.get_by_id = AsyncMock(return_value=device)
    return mock


@pytest.fixture(name="process_compose_fixture")
def process_compose(conf, config_fixture):

    pc_kwargs = {
        "config": config_fixture,
        "daemon_name": "process-compose",
        "daemon_bin": conf.PROCESS_COMPOSE_BIN,
        "daemon_config": conf.config_dir / "process-compose.yaml",
        "daemon_log": conf.log_dir / "process-compose.log",
        "daemon_socket": conf.run_dir / "process-compose.sock",
        "data_dir": conf.data_dir,
        "uv_bin": conf.UV_BIN,
    }
    return ProcessComposeFactory.build(factory_use_construct=True, **pc_kwargs)
