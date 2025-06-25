import json

import pydantic
import structlog
from aiopath import AsyncPath

from pikesquares import caddy_client, services
from pikesquares.conf import AppConfig, AppConfigError
from pikesquares.domain.process_compose import (
    CaddyProcess,
    Process,
    ProcessAvailability,
    ProcessMessages,
)
from pikesquares.exceptions import ServiceUnavailableError

#from pikesquares.domain.managed_services import ManagedServiceBase
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.get_logger()


class CaddyUnavailableError(ServiceUnavailableError):
    pass


caddy_config_initial = """{
  "apps": {
    "http": {
      "https_port": 443,
      "servers": {}
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

"""
    "servers": {
        "*.pikesquares.local": {
            "listen": [":443", "unix//path/to/socket|0200"],
            "routes": [{
                "@id": "http-router-123",
                "match": [{"host": ["*.pikesquares.local"]}],
                "handle": [{
                    "handler": "reverse_proxy",
                    // https://github.com/wxh06/caddy-uwsgi-transport
                    // "transport": {"protocol": "uwsgi"},
                    "transport": {"protocol": "http"},
                    "upstreams": [{"dial": "127.0.0.1:8034"}]
                }]
            }]
        }
    }
"""

class RouteMatch(pydantic.BaseModel):
    host: list[str]

class HandlerUpstream(pydantic.BaseModel):
    #{"dial": "127.0.0.1:8035"}
    dial: str

class RouteHandler(pydantic.BaseModel):
    handler: str = "reverse_proxy"
    transport: dict = {"protocol": "http"}
    upstreams: list[HandlerUpstream]

class Route(pydantic.BaseModel):
    id: str = pydantic.Field(serialization_alias="@id")
    match: list[RouteMatch]
    handle: list[RouteHandler]

class Server(pydantic.BaseModel):
    routes: list[Route]
    listen: list[str] = [":443"]

class AppHttp(pydantic.BaseModel):
    https_port: int = 443
    servers: dict[str, Server] = {}

class App(pydantic.BaseModel):
    http: AppHttp
    tls: dict = {"automation":{ "policies":[{ "issuers":[{ "module":"internal"}]}]}}

class CaddyConfig(pydantic.BaseModel):
    apps: App
    storage: dict = {"module": "file_system", "root": "/var/lib/pikesquares/caddy"}


def caddy_close():
    pass
    #logger.debug("caddy closed")

async def caddy_ping(caddy_data: tuple[CaddyProcess, ProcessMessages]):
    process, msgs = caddy_data
    # raise ServiceUnavailableError("dnsmasq down")
    return True


async def register_caddy_process(context: dict) -> None:
    """register caddy"""

    # caddy
    async def caddy_process_factory(svcs_container) -> tuple[CaddyProcess, ProcessMessages]:
        """Caddy process-compose process"""

        conf = await svcs_container.aget(AppConfig)
        uow = await svcs_container.aget(UnitOfWork)

        if conf.CADDY_BIN and not await AsyncPath(conf.CADDY_BIN).exists():
            raise AppConfigError(f"unable locate caddy binary @ {conf.CADDY_BIN}") from None

        #await AsyncPath(conf.caddy_config_path).write_text(caddy_config_initial)
        routers = await uow.http_routers.list()
        #if routers:
        with open(conf.caddy_config_path, "r+") as caddy_config:
            #vhost_key = "*.pikesquares.local"
            # data = json.load(caddy_config)
            data = json.loads(caddy_config_initial)
            servers = data["apps"]["http"]["servers"]
            #routes = apps.get("http").get("servers").get(vhost_key).get("routes")
            #handles = routes[0].get("handle")
            #upstreams = handles[0].get("upstreams")
            #upstream_address = upstreams[0].get("dial")
            #if upstream_address != f"{http_router_ip}:{http_router_port}":
            #          data["apps"]["http"]["servers"][vhost_key]["routes"]
            #          [0]["handle"]
            #          [0]["upstreams"]
            #          [0]["dial" ] = "{http_router.address}"
            #
            routes = []
            for router in routers:
                routes.append({
                    "@id": router.service_id,
                    "match": [{"host": ["*.pikesquares.local"]}],
                    "handle": [{
                        "handler": "reverse_proxy",
                        #// https://github.com/wxh06/caddy-uwsgi-transport
                        #// "transport": {"protocol": "uwsgi"},
                        "transport": {"protocol": "http"},
                        "upstreams": [
                            {"dial": router.address}
                        ]
                    }]
                })
            servers["*.pikesquares.local"] = {
                "listen": [":443"],
                "routes": routes,
            }
            caddy_config.seek(0)
            json.dump(data, caddy_config)
            caddy_config.truncate()

        process_messages = ProcessMessages(
            title_start="!! caddy start title !!",
            title_stop="!! caddy stop title !!",
        )
        process = Process(
            disabled=not conf.CADDY_ENABLED,
            description="reverse proxy",
            
            command=f"{conf.CADDY_BIN} run --pidfile {conf.run_dir / 'caddy.pid'} --config {conf.caddy_config_path}",
            working_dir=conf.data_dir,
            availability=ProcessAvailability(),
            # readiness_probe=ReadinessProbe(
            #    http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
            # ),
        )
        return process, process_messages

    services.register_factory(
        context,
        CaddyProcess,
        caddy_process_factory,
        ping=caddy_ping,
        on_registry_close=caddy_close,
    )

"""
class Caddy(ManagedServiceBase):

    daemon_name: str = "caddy"

    cmd_args: list[str] = []
    cmd_env: dict[str, str] = {}

    # "${CADDY_BIN} reverse-proxy --from :2080 --to :8034"

    def __repr__(self) -> str:
        return "caddy"

    def __str__(self) -> str:
        return self.__repr__()

    def up(self) -> tuple[int, str, str]:
        cmd_args = [
            "reverse-proxy",
            "--from",
            ":2080",
            "--to",
            ":8034",
        ]
        cmd_env = {}
        try:
            return self.cmd(
                cmd_args,
                cmd_env=cmd_env,
            )

        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    def down(self) -> tuple[int, str, str]:

        try:
            cmd_args = []
            cmd_env = {}
            return self.cmd(
                cmd_args,
                cmd_env=cmd_env,
            )
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr
"""

if __name__ == "__main__":

    conf_one = """\
    {
        "apps": {
            "http": {
            "https_port": 443,
            "servers": {
                "*.pikesquares.local": {
                "listen": [":443"],
                "routes": [
                    {
                    "match": [{"host": ["*.pikesquares.local"]}],
                    "handle": [
                        {
                        "handler": "reverse_proxy",
                        "transport": {"protocol": "http"},
                        "upstreams": [{"dial": "127.0.0.1:8035"}]
                        }
                    ]
                    }
                ]
                }
            }
            },
            "tls": {"automation": {"policies": [{"issuers": [{"module": "internal"}]}]}
            }
        },
        "storage": {
            "module": "file_system",
            "root": "/var/lib/pikesquares/caddy"
        }
    }"""

    #caddy_conf_one = CaddyConfig.model_validate(json.loads(conf_one))
    #import ipdb;ipdb.set_trace()

    client = caddy_client.CaddyAPIClient("http://localhost:2019")

    # Example domain and backend service
    domain = "example.com"  # Replace with your actual domain
    target = "nginx"  # Docker service name will resolve to container IP
    target_port = 80  # Replace with your backend service port

    try:
        # Read certificate and key PEM files
        with open('tls.crt', 'r') as f:
            certificate = f.read()
        with open('tls.key', 'r') as f:
            private_key = f.read()

        # Add domain with PEM certificate
        client.add_domain_with_tls(
            domain=domain,
            target=target,
            target_port=target_port,
            certificate=certificate,
            private_key=private_key
        )
        print(f"Successfully added domain {domain} with PEM certificate")

        # Show domain configuration
        config = client.get_domain_config(domain)
        print("\nDomain configuration:")
        print(config)

    except Exception as e:
        print(f"Error: {e}")

