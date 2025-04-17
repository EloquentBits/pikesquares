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
from pikesquares.conf import AppConfig, AppConfigError, ensure_system_path
from pikesquares.domain.device import Device
from pikesquares.domain.managed_services import ManagedServiceBase
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.get_logger()


class ServiceUnavailableError(Exception):
    pass


class PCAPIUnavailableError(ServiceUnavailableError):
    pass


class ProcessStats(pydantic.BaseModel):

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


class ProcessMessages(pydantic.BaseModel):
    title_start: str
    title_stop: str


class Process(pydantic.BaseModel):
    """process-compose process"""

    description: str
    command: str
    is_elevated: bool = False
    working_dir: Annotated[pydantic.DirectoryPath, pydantic.Field()] | None = None
    availability: ProcessAvailability
    readiness_probe: ReadinessProbe | None = None
    disabled: bool = False
    is_daemon: bool = False
    # depends_on: list["Process"] = []


class Config(pydantic.BaseModel):
    """process-compose process config (yaml)"""

    version: str = "0.1"
    is_strict: bool = True
    log_level: str = "debug"
    processes: dict[str, Process]
    custom_messages: dict[str, ProcessMessages]


class ProcessCompose(ManagedServiceBase):

    daemon_name: str = "process-compose"
    config: Config

    uv_bin: Annotated[pydantic.FilePath, pydantic.Field()]

    cmd_args: list[str] = []
    cmd_env: dict[str, str] = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cmd_args = ["--unix-socket", str(self.daemon_socket)]
        self.cmd_env = {
            # TODO use shellingham library
            "COMPOSE_SHELL": os.environ.get("SHELL"),
        }

    def __repr__(self) -> str:
        return "process-compose"

    def __str__(self) -> str:
        return self.__repr__()

    async def write_config_to_disk(self) -> None:
        if self.daemon_config:  # and await AsyncPath(self.daemon_config).exists():
            config = AsyncPath(self.daemon_config)
            await config.write_text(to_yaml_str(self.config, exclude={"custom_messages"}))
            # import ipdb

            # ipdb.set_trace()

    async def reload(self):
        """docket-compose project update"""
        if not self.daemon_socket or not await AsyncPath(self.daemon_socket).exists():
            raise PCAPIUnavailableError()

        await self.write_config_to_disk()

        try:
            self.cmd_args.insert(0, "project")
            self.cmd_args.insert(1, "update")
            return self.cmd(self.cmd_args, cmd_env=self.cmd_env)
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    async def up(self) -> bool:
        # always write config to dist before starting
        #
        await self.write_config_to_disk()
        args = [
            "up",
            "--config",
            str(self.daemon_config),
            "--log-file",
            str(self.daemon_log),
            "--detached",
            "--hide-disabled",
        ] + self.cmd_args
        try:
            retcode, stdout, stderr = self.cmd(args, cmd_env=self.cmd_env)
            if retcode:
                logger.debug(retcode)
            if stdout:
                logger.debug(stdout)
            if stderr:
                logger.error(stderr)
            # if retcode != 0:
            #    logger.error(retcode, stdout, stderr)
            #    return False
        except ProcessExecutionError as exc:
            logger.error(exc)
            return False

        # try:
        #    logger.debug(f"setting perms on {self.daemon_socket}")
        #    ensure_system_path(self.daemon_socket, is_dir=False)
        #    if self.daemon_socket:
        #        logger.debug(f"set perms on {self.daemon_socket} to {oct(self.daemon_socket.stat().st_mode)}")
        # except AppConfigError:
        #    logger.error("unable to set perms on process compose socket")
        #    return False
        return True

    async def down(self) -> tuple[int, str, str]:
        if self.daemon_socket and not await AsyncPath(self.daemon_socket).exists():
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
            raise PCAPIUnavailableError("unable to reach Process Compose API")

    async def ping_api(self, process_name: str) -> ProcessStats:
        if self.daemon_socket and not await AsyncPath(self.daemon_socket).exists():
            raise PCAPIUnavailableError("unable to reach Process Compose API")

        try:
            cmd_args = ["process", "list", "--output", "json"]
            _, stdout, _ = self.cmd(cmd_args + self.cmd_args, cmd_env=self.cmd_env)
        except ProcessExecutionError as exc:
            logger.error(exc)
            raise PCAPIUnavailableError("unable to reach Process Compose API")

        try:
            return ProcessStats(**next(filter(lambda p: p.get("name") == process_name, json.loads(stdout))))
        except (IndexError, StopIteration):
            pass

        raise PCAPIUnavailableError()


# factories
async def make_api_process(conf: AppConfig) -> tuple[Process, ProcessMessages]:
    """FastAPI process-compose process"""

    api_port = 9544
    # cmd = f"{conf.UV_BIN} run fastapi dev --port {api_port} src/pikesquares/app/main.py"
    cmd = f"{conf.UV_BIN} run uvicorn pikesquares.app.main:app --host 0.0.0.0 --port {api_port}"

    process_messages = ProcessMessages(
        title_start="!! api start title !!!",
        title_stop="abc",
    )
    process = Process(
        description="PikeSquares API",
        command=cmd,
        working_dir=conf.data_dir,
        availability=ProcessAvailability(),
        readiness_probe=ReadinessProbe(http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)),
    )
    return process, process_messages


async def make_device_process(device: Device, conf: AppConfig) -> tuple[Process, ProcessMessages]:
    """device process-compose process"""

    # if not AsyncPath(conf.sqlite_plugin_path).exists():
    #    sqlite_plugin_alt = os.environ.get("PIKESQUARES_SQLITE_PLUGIN")
    #    if sqlite_plugin_alt and AsyncPath(sqlite_plugin_alt).exists():
    #        sqlite_plugin_path = AsyncPath(sqlite_plugin_alt)
    #    else:
    #        raise AppConfigError(f"unable locate sqlite uWSGI plugin @ {sqlite_plugin_path}") from None

    cmd = f"{conf.UWSGI_BIN} --show-config --plugin {str(conf.sqlite_plugin)} --sqlite {str(conf.db_path)}:"
    sql = (
        f'"SELECT option_key,option_value FROM uwsgi_options WHERE device_id=\'{device.id}\' ORDER BY sort_order_index"'
    )
    process = Process(
        description="Device Manager",
        command="".join([cmd, sql]),
        working_dir=conf.data_dir,
        availability=ProcessAvailability(),
        # readiness_probe=ReadinessProbe(
        #    http_get=ReadinessProbeHttpGet()
        # ),
    )
    messages = ProcessMessages(
        title_start="!! device start title !!",
        title_stop="!! device stop title !!",
    )

    return process, messages


# caddy
async def make_caddy_process(conf: AppConfig, http_router_port=int) -> tuple[Process, ProcessMessages]:
    """Caddy process-compose process"""

    if conf.CADDY_BIN and not await AsyncPath(conf.CADDY_BIN).exists():
        raise AppConfigError(f"unable locate caddy binary @ {conf.CADDY_BIN}") from None

    # await AsyncPath(conf.caddy_config_path).write_text(conf.caddy_config_initial)

    with open(conf.caddy_config_path, "r+") as caddy_config:
        vhost_key = "*.pikesquares.local"
        # data = json.load(caddy_config)
        data = json.loads(conf.caddy_config_initial)
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

    process_messages = ProcessMessages(
        title_start="!! caddy start title !!",
        title_stop="!! caddy stop title !!",
    )
    process = Process(
        description="reverse proxy",
        command=f"{conf.CADDY_BIN} run --config {conf.caddy_config_path} --pidfile {conf.run_dir / 'caddy.pid'}",
        working_dir=conf.data_dir,
        availability=ProcessAvailability(),
        # readiness_probe=ReadinessProbe(
        #    http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
        # ),
    )
    return process, process_messages


# dnsmasq
async def make_dnsmasq_process(
    conf: AppConfig,
    port: int = 5353,
    addresses: list[str] | None = None,
    listen_address: str = "127.0.0.34",
    # http_router_port=int,
) -> tuple[Process, ProcessMessages]:
    """dnsmasq process-compose process"""

    if conf.DNSMASQ_BIN and not await AsyncPath(conf.DNSMASQ_BIN).exists():
        raise AppConfigError(f"unable locate dnsmasq binary @ {conf.DNSMASQ_BIN}") from None

    cmd = f"{conf.DNSMASQ_BIN} --keep-in-foreground --port {port} --listen-address {listen_address} --no-resolv"
    for addr in addresses or ["/pikesquares.local/192.168.0.1"]:
        cmd = cmd + f" --address {addr}"

    process_messages = ProcessMessages(
        title_start="!!! dnsmasq start title !!!",
        title_stop="abc",
    )
    process = Process(
        description="dns resolver",
        command=cmd,
        working_dir=conf.data_dir,
        availability=ProcessAvailability(),
        # readiness_probe=ReadinessProbe(
        #    http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
        # ),
    )
    return process, process_messages


async def register_process_compose(context: dict) -> None:
    """process-compose factory"""

    uow = await services.aget(context, UnitOfWork)
    conf = services.get(context, AppConfig)
    device = context.get("device")
    if not device:
        raise AppConfigError("no device found in context")

    http_router = context.get("default-http-router")
    if not http_router:
        raise AppConfigError("no http router found in context")

    if conf.UV_BIN and not await AsyncPath(conf.UV_BIN).exists():
        raise AppConfigError(f"unable locate uv binary @ {conf.UV_BIN}") from None

    if conf.UWSGI_BIN and not await AsyncPath(conf.UWSGI_BIN).exists():
        raise AppConfigError(f"unable locate uWSGI binary @ {conf.UWSGI_BIN}") from None

    api_process, api_messages = await make_api_process(conf)
    device_process, device_messages = await make_device_process(device, conf)
    caddy_process, caddy_messages = await make_caddy_process(conf, http_router.port)
    dnsmasq_process, dnsmasq_messages = await make_dnsmasq_process(conf)

    pc_config = Config(
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
        return ProcessCompose(**pc_kwargs)

    services.register_factory(
        context,
        ProcessCompose,
        process_compose_factory,
        # ping=svc: await svc.ping(),
    )
