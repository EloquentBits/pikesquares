import json
import os
from enum import Enum
from pathlib import Path
from typing import Annotated

import pydantic
import structlog
from aiopath import AsyncPath
from plumbum import ProcessExecutionError
from pydantic_yaml import to_yaml_str

from pikesquares import services
from pikesquares.conf import AppConfig, AppConfigError
from pikesquares.domain.device import Device
from pikesquares.domain.managed_services import ManagedServiceBase
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.services.base import ServiceUnavailableError

# from pikesquares.services import register_factory

logger = structlog.get_logger()


class PCAPIUnavailableError(ServiceUnavailableError):
    pass


class PCDeviceUnavailableError(ServiceUnavailableError):
    pass


class ProcessComposeProcessStats(pydantic.BaseModel):

    IsRunning: bool
    age: int
    cpu: float
    exit_code: int
    is_elevated: bool
    is_ready: str
    mem: int
    name: str
    namespace: str
    password_provided: bool
    pid: int
    restarts: int
    status: str
    system_time: str


class ProcessRestart(str, Enum):
    """process-compose process restart options"""

    no = "no"  # default
    yes = "yes"
    on_failure = "on_failure"
    exit_on_failure = ("exit_on_failure",)
    always = "always"


class ProcessAvailability(pydantic.BaseModel):
    """process-compose process availability options"""

    restart: str = ProcessRestart.yes
    exit_on_end: str = "no"
    backoff_seconds: int = 2
    max_restarts: int = 5


class ReadinessProbeHttpGet(pydantic.BaseModel):
    """process-compose readiness probe http get section"""

    host: str = "127.0.0.1"
    scheme: str = "http"
    path: str = "/"
    port: int = 9544


class ReadinessProbe(pydantic.BaseModel):
    """process-compose readiness probe section"""

    http_get: ReadinessProbeHttpGet
    initial_delay_seconds: int = 5
    period_seconds: int = 10
    timeout_seconds: int = 5
    success_threshold: int = 1
    failure_threshold: int = 3


class ProcessComposeProcess(pydantic.BaseModel):
    """process-compose process"""

    description: str
    command: str
    is_elevated: bool = False
    working_dir: Annotated[pydantic.DirectoryPath, pydantic.Field()] | None = None
    availability: ProcessAvailability
    readiness_probe: ReadinessProbe | None = None
    disabled: bool = False
    is_daemon: bool = False
    # depends_on: list["ProcessComposeProcess"] = []


class ProcessComposeConfig(pydantic.BaseModel):
    """process-compose process config (yaml)"""

    version: str = "0.1"
    is_strict: bool = True
    log_level: str = "debug"
    processes: dict[str, ProcessComposeProcess]


class ProcessCompose(ManagedServiceBase):

    daemon_name: str = "process-compose"
    config: ProcessComposeConfig

    uv_bin: Annotated[pydantic.FilePath, pydantic.Field()]

    cmd_args: list[str] = []
    cmd_env: dict[str, str] = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cmd_args = [
            "--use-uds",
            "--unix-socket",
            self.daemon_socket,
        ]
        self.cmd_env = {
            # TODO use shellingham library
            "COMPOSE_SHELL": os.environ.get("SHELL"),
        }

    def __repr__(self) -> str:
        return "process-compose"

    def __str__(self) -> str:
        return self.__repr__()

    # @pydantic.computed_field
    # async def get_socket_address(self) -> AsyncPath:
    #    return await AsyncPath(
    #        self.conf.run_dir) / "process-compose.sock"

    async def write_config_to_disk(self):
        if self.daemon_config:
            config = AsyncPath(self.daemon_config)
            await config.write_text(to_yaml_str(self.config))

    async def reload(self):
        """docket-compose project update"""
        if not self.daemon_socket or not await AsyncPath(self.daemon_socket).exists():
            raise PCAPIUnavailableError()

        await self.write_config_to_disk()

        try:
            self.cmd_args.insert(0, "project")
            self.cmd_args.insert(1, "update")
            return self.cmd(
                self.cmd_args,
                cmd_env=self.cmd_env,
            )
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    async def up(self) -> tuple[int, str, str]:
        # always write config to dist before starting
        await self.write_config_to_disk()
        args = [
            "up",
            "--config",
            str(self.daemon_config),
            "--log-file",
            str(self.daemon_log),
            "--detached",
            "--hide-disabled",
            # "--tui",
            # "false",
        ] + self.cmd_args

        try:
            return self.cmd(args, cmd_env=self.cmd_env)
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    async def down(self) -> tuple[int, str, str]:
        if self.daemon_socket and not self.daemon_socket.exists():
            raise PCAPIUnavailableError()

        try:
            cmd_args = self.cmd_args.insert(0, "down")
            return self.cmd(
                self.cmd_args,
                cmd_env=self.cmd_env,
            )
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    def attach(self) -> tuple[int, str, str]:
        if self.daemon_socket and not self.daemon_socket.exists():
            raise PCAPIUnavailableError()

        try:
            return self.cmd(
                self.cmd_args.insert(0, "attach"),
                cmd_env=self.cmd_env,
            )
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    def ping(self) -> None:
        if self.daemon_socket and not self.daemon_socket.exists():
            raise PCAPIUnavailableError()

    def ping_api(self) -> bool:
        if self.daemon_socket and not self.daemon_socket.exists():
            raise PCAPIUnavailableError()

        try:
            cmd_args = [
                "process",
                "list",
                "--output",
                "json",
            ]
            _, stdout, _ = self.cmd(
                cmd_args + self.cmd_args,
                cmd_env=self.cmd_env,
            )
            js = json.loads(stdout)
            try:
                device_process = next(filter(lambda p: p.get("name") in ["device", "api"], js))
                process_stats = ProcessComposeProcessStats(**device_process)
                if process_stats.IsRunning and process_stats.status == "Running":
                    return True
            except (IndexError, StopIteration):
                pass
        except ProcessExecutionError as exc:
            logger.error(exc)
            return False

        raise PCDeviceUnavailableError()


# factories
async def make_api_process(conf: AppConfig) -> ProcessComposeProcess:
    """FastAPI process-compose process"""

    api_port = 9544
    # cmd = f"{conf.UV_BIN} run fastapi dev --port {api_port} src/pikesquares/app/main.py"
    cmd = f"{conf.UV_BIN} run uvicorn pikesquares.app.main:app --host 0.0.0.0 --port {api_port}"

    return ProcessComposeProcess(
        description="PikeSquares FastAPI",
        command=cmd,
        working_dir=conf.PYTHON_VIRTUAL_ENV or Path().cwd(),
        availability=ProcessAvailability(),
        readiness_probe=ReadinessProbe(http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)),
    )


async def make_device_process(context: dict, device: Device, conf: AppConfig) -> ProcessComposeProcess:
    """device process-compose process"""
    sqlite3_plugin = conf.plugins_dir / "sqlite3_plugin.so"
    if not sqlite3_plugin.exists():

        sqlite_plugin_alt = os.environ.get("PIKESQUARES_SQLITE_PLUGIN")
        if sqlite_plugin_alt and Path(sqlite_plugin_alt).exists():
            sqlite3_plugin = Path(sqlite_plugin_alt)
        else:
            raise AppConfigError(f"unable locate sqlite uWSGI plugin @ {str(sqlite3_plugin)}") from None

    sqlite3_db = conf.data_dir / "pikesquares.db"
    cmd = f"{conf.UWSGI_BIN} --plugin {str(sqlite3_plugin)} --sqlite {str(sqlite3_db)}:"
    sql = (
        f'"SELECT option_key,option_value FROM uwsgi_options WHERE device_id=\'{device.id}\' ORDER BY sort_order_index"'
    )

    uow = await services.aget(context, UnitOfWork)
    uwsgi_options = await uow.uwsgi_options.get_by_device_id(device.id)
    logger.debug(f"read {len(uwsgi_options)} uwsgi options for device {device.id}")
    if not uwsgi_options:
        raise AppConfigError("unable to read uwsgi options for device {device.id}")

    return ProcessComposeProcess(
        description="PikeSquares Server",
        command="".join([cmd, sql]),
        working_dir=Path().cwd(),
        availability=ProcessAvailability(),
        # readiness_probe=ReadinessProbe(
        #    http_get=ReadinessProbeHttpGet()
        # ),
    )


# caddy
async def make_caddy_process(
    conf: AppConfig,
    http_router_port=int,
) -> ProcessComposeProcess:
    """Caddy process-compose process"""

    if conf.CADDY_BIN and not await AsyncPath(conf.CADDY_BIN).exists():
        raise AppConfigError(f"unable locate caddy binary @ {conf.CADDY_BIN}") from None

    caddy_config_file = AsyncPath(conf.config_dir) / "caddy.json"
    vhost_key = "*.pikesquares.local"
    if not await caddy_config_file.exists():
        caddy_config_default = """{"apps": {"http": {"https_port": 443, "servers": {"*.pikesquares.local": {"listen": [":443"], "routes": [{"match": [{"host": ["*.pikesquares.local"]}], "handle": [{"handler": "reverse_proxy", "transport": {"protocol": "http"}, "upstreams": [{"dial": "127.0.0.1:8035"}]}]}]}}}, "tls": {"automation": {"policies": [{"issuers": [{"module": "internal"}]}]}}}, "storage": {"module": "file_system", "root": "/var/lib/pikesquares/caddy"}}"""
        await caddy_config_file.write_text(caddy_config_default)

    with open(caddy_config_file, "r+") as caddy_config:
        data = json.load(caddy_config)
        apps = data.get("apps")
        routes = apps.get("http").get("servers").get(vhost_key).get("routes")
        handles = routes[0].get("handle")
        upstreams = handles[0].get("upstreams")
        upstream_address = upstreams[0].get("dial")
        if upstream_address != f"127.0.0.1:{http_router_port}":
            data["apps"]["http"]["servers"][vhost_key]["routes"][0]["handle"][0]["upstreams"][0][
                "dial"
            ] = f"127.0.0.1:{http_router_port}"
            caddy_config.seek(0)
            json.dump(data, caddy_config)
            caddy_config.truncate()

    return ProcessComposeProcess(
        description="PikeSquares Caddy",
        command=f"{conf.CADDY_BIN} run --config {caddy_config_file} --pidfile {conf.run_dir / 'caddy.pid'}",
        working_dir=Path().cwd(),
        availability=ProcessAvailability(),
        # readiness_probe=ReadinessProbe(
        #    http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
        # ),
    )


# dnsmasq
def make_dnsmasq_process(
    conf: AppConfig,
    # http_router_port=int,
) -> ProcessComposeProcess:
    """dnsmasq process-compose process"""

    # "${DNSMASQ_BIN} --keep-in-foreground --port 5353 --address=/pikesquares.local/192.168.0.1 --address=/pikesquares.dev/192.168.0.1 --listen-address=127.0.0.34 --no-resolv"

    if not all([conf.DNSMASQ_BIN, conf.DNSMASQ_BIN.exists()]):
        raise AppConfigError(f"unable locate dnsmasq binary @ {conf.DNSMASQ_BIN}") from None

    cmd_args = [
        "--keep-in-foreground",
        "--port 5353",
        "--address=/pikesquares.local/192.168.0.1",
        "--listen-address=127.0.0.34",
        "--no-resolv",
    ]
    cmd = f"{conf.DNSMASQ_BIN}  --keep-in-foreground --port 5353 --address=/pikesquares.local/192.168.0.1 --address=/pikesquares.dev/192.168.0.1 --listen-address=127.0.0.34 --no-resolv"

    return ProcessComposeProcess(
        description="PikeSquares dnsmasq",
        command=cmd,
        working_dir=Path().cwd(),
        availability=ProcessAvailability(),
        # readiness_probe=ReadinessProbe(
        #    http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
        # ),
    )


async def register_process_compose(context: dict, conf: AppConfig) -> None:
    """process-compose factory"""

    device = context.get("device")
    if not device:
        raise AppConfigError("no device found in context")

    http_router = context.get("default-http-router")
    if not http_router:
        raise AppConfigError("no http router found in context")

    if not all([conf.UV_BIN, conf.UV_BIN.exists()]):
        raise AppConfigError(f"unable locate uv binary @ {conf.UV_BIN}") from None

    if not all([conf.UWSGI_BIN, conf.UWSGI_BIN.exists()]):
        raise AppConfigError(f"unable locate uWSGI binary @ {conf.UWSGI_BIN}") from None

    pc_config = ProcessComposeConfig(
        processes={
            "api": await make_api_process(conf),
            "device": await make_device_process(context, device, conf),
            "caddy": await make_caddy_process(conf, http_router.port),
        },
    )
    pc_kwargs = {
        "config": pc_config,
        "daemon_name": "process-compose",
        "daemon_bin": conf.PROCESS_COMPOSE_BIN,
        "daemon_config": conf.config_dir / "process-compose.yaml",
        "daemon_log": conf.log_dir / "process-compose.log",
        "daemon_socket": conf.run_dir / "process-compose.sock",
        "data_dir": conf.data_dir,
        "uv_bin": conf.UV_BIN,
    }

    def process_compose_factory() -> ProcessCompose:
        # if ctx.invoked_subcommand == "up":
        #    dc = pc_kwargs.get("daemon_config")
        #    if dc:
        #        dc.touch(mode=0o666, exist_ok=True)

        """
        owner_username = "root"
        owner_groupname = "pikesquares"
        try:
            owner_uid = pwd.getpwnam("root")[2]
        except KeyError:
            raise AppConfigError(f"unable locate user: {owner_username}") from None

        try:
            owner_gid = grp.getgrnam(owner_groupname)[2]
        except KeyError:
            raise AppConfigError(f"unable locate group: {owner_groupname}") from None

        os.chown(dc, owner_uid, owner_gid)
        """

        return ProcessCompose(**pc_kwargs)

    services.register_factory(
        context,
        ProcessCompose,
        process_compose_factory,
        # ping=svc: await svc.ping(),
    )
