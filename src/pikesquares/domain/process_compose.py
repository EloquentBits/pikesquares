import grp
import json
import os
from asyncio import sleep
from enum import Enum
from pathlib import Path
from typing import Annotated, NewType

import pydantic
import structlog
from aiopath import AsyncPath
from plumbum import ProcessExecutionError
from pydantic_yaml import to_yaml_str
from svcs.exceptions import ServiceNotFoundError

from pikesquares import services
from pikesquares.conf import AppConfig, AppConfigError
from pikesquares.domain.managed_services import ManagedServiceBase
from pikesquares.service_layer.handlers.routers import http_router_ips
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.get_logger()


class ServiceUnavailableError(Exception):
    pass


class PCAPIUnavailableError(ServiceUnavailableError):
    pass


class ProcessStats(pydantic.BaseModel):

    is_running: bool
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

    on_failure = "on_failure"
    exit_on_failure = ("exit_on_failure",)
    always = "always"


class ProcessAvailability(pydantic.BaseModel):
    """process-compose process availability options"""

    restart: str = ProcessRestart.always
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

    cmd_args: list[str] | None = None
    cmd_env: dict[str, str] | None = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cmd_args = ["--unix-socket", str(self.daemon_socket)]
        self.cmd_env : dict[str, str] = {}
        # TODO use shellingham library
        shell_path = os.environ.get("SHELL")
        if shell_path:
            self.cmd_env["COMPOSE_SHELL"] = shell_path

    def __repr__(self) -> str:
        return "process-compose"

    def __str__(self) -> str:
        return self.__repr__()

    async def write_config_to_disk(self) -> None:
        if self.daemon_config:
            await AsyncPath(self.daemon_config).\
            write_text(to_yaml_str(self.config, exclude={"custom_messages"}))

    async def add_tail_log_process(self, name: str, logfile: Path) -> None:
        """
        create a process compose process that tails the service log file
        """

        if not logfile.exists():
            logger.info(f"{logfile} does not exist yet. sleeping")
            await sleep(5)

        if not logfile.exists():
            logger.info(f"{logfile} does not exist yet. giving up")
            return

        self.config.processes["-".join([name, "logs"])] = Process(
                description=f"logfile {name}",
                disabled=False,
                command=f"tail -f {logfile}",
                working_dir=self.data_dir,
                availability=ProcessAvailability(),
                # readiness_probe=ReadinessProbe(
                #    http_get=ReadinessProbeHttpGet()
                # ),
        )
        await self.reload()

    async def reload(self):
        """docket-compose project update"""
        await self.write_config_to_disk()
        logger.info("new config. reloading process compose")
        try:
            self.cmd_args.insert(0, "project")
            self.cmd_args.insert(1, "update")
            self.cmd_args.insert(2, "--config")
            self.cmd_args.insert(3, str(self.daemon_config))

            return self.cmd(
                self.cmd_args,
                cmd_env=self.cmd_env
            )
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    async def up(self) -> bool | tuple[str, str, str]:
        # always write config to dist before starting
        #
        await self.write_config_to_disk()

        # Set the current numeric umask and return the previous umask.
        old_umask = os.umask(0o002)
        os.setgid(grp.getgrnam("pikesquares")[2])
        try:
            return self.cmd([
                "up",
                "--config",
                str(self.daemon_config),
                "--log-file",
                str(self.daemon_log),
                "--detached",
                "--hide-disabled",
            ] + self.cmd_args,
            cmd_env=self.cmd_env)
        except ProcessExecutionError as exc:
            logger.error(exc)
            return False
        finally:
            os.umask(old_umask)

    async def down(self) -> tuple[str, str, str]:
        if self.daemon_socket and not await AsyncPath(self.daemon_socket).exists():
            raise PCAPIUnavailableError()

        try:
            return self.cmd(
                ["down", * self.cmd_args],
                cmd_env=self.cmd_env,
            )
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    def attach(self) -> tuple[str, str, str]:
        if self.daemon_socket and not self.daemon_socket.exists():
            raise PCAPIUnavailableError()

        try:
            return self.cmd(
                ["attach", * self.cmd_args],
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

APIProcess = NewType("APIProcess", Process)
DeviceProcess = NewType("DeviceProcess", Process)
DNSMASQProcess = NewType("DNSMASQProcess", Process)
CaddyProcess = NewType("CaddyProcess", Process)
# DeviceProcessMessages = NewType("DeviceProcessMessages", ProcessMessages)


async def process_compose_ping(pc: ProcessCompose):
    # raise ServiceUnavailableError("process compose down")
    return True


async def register_process_compose(
    context: dict,
    machine_id: str,
    uow: UnitOfWork,
) -> None:
    """process-compose factory"""

    from pikesquares.domain.caddy import register_caddy_process
    from pikesquares.domain.device import register_device_stats
    from pikesquares.domain.dnsmasq import register_dnsmasq_process

    svcs_container = context["svcs_container"]
    conf = await svcs_container.aget(AppConfig)

    await register_device_process(context, machine_id)
    http_router_addresses = await http_router_ips(uow)
    if http_router_addresses:
        await register_dnsmasq_process(context, addresses=http_router_addresses)

    routers = await uow.http_routers.list()
    if routers:
        await register_caddy_process(context)

    #await register_api_process(context)
    await register_device_stats(context)
    pc_processes = {}
    pc_msgs = {}
    try:
        pc_processes["device"] , pc_msgs["device"] = await svcs_container.aget(DeviceProcess)
    except ServiceNotFoundError:
        pass

    try:
        pc_processes["caddy"], pc_msgs["caddy"] = await svcs_container.aget(CaddyProcess)
    except ServiceNotFoundError:
        pass

    try:
        pc_processes["dnsmasq"], pc_msgs["dnsmasq"] = await svcs_container.aget(DNSMASQProcess)
    except ServiceNotFoundError:
        pass

    try:
        pc_processes["api"], pc_msgs["api"] = await svcs_container.aget(APIProcess)
    except ServiceNotFoundError:
        pass

    pc_config = Config(
        processes=pc_processes,
        custom_messages=pc_msgs,
    )
    pc_kwargs = {
        "config": pc_config,
        "daemon_name": "process-compose",
        "daemon_bin": conf.PROCESS_COMPOSE_BIN,
        "daemon_config": conf.config_dir / "process-compose.yaml",
        #"daemon_log": conf.log_dir / "process-compose.log",
        #"daemon_socket": conf.run_dir / "process-compose.sock",
        "data_dir": conf.data_dir,
        "run_dir": conf.run_dir,
        "log_dir": conf.log_dir,
        "uv_bin": conf.UV_BIN,
    }

    async def process_compose_factory() -> ProcessCompose:
        return ProcessCompose(**pc_kwargs)

    services.register_factory(
        context,
        ProcessCompose,
        process_compose_factory,
        ping=process_compose_ping,
        # ping=svc: await svc.ping(),
    )


def device_close():
    ...
    #logger.debug("device closed")


async def device_ping(device_data: tuple[DeviceProcess, ProcessMessages]):
    process, msgs = device_data
    # raise ServiceUnavailableError("dnsmasq down")
    return True


async def register_device_process(context: dict, machine_id: str) -> None:
    """register device"""

    async def device_process_factory(svcs_container) -> tuple[Process, ProcessMessages] | None:
        """device process-compose process"""

        # if not AsyncPath(conf.sqlite_plugin_path).exists():
        #    sqlite_plugin_alt = os.environ.get("PIKESQUARES_SQLITE_PLUGIN")
        #    if sqlite_plugin_alt and AsyncPath(sqlite_plugin_alt).exists():
        #        sqlite_plugin_path = AsyncPath(sqlite_plugin_alt)
        #    else:
        #        raise AppConfigError(f"unable locate sqlite uWSGI plugin @ {sqlite_plugin_path}") from None
        #
        conf = await svcs_container.aget(AppConfig)
        cmd = f"{conf.UWSGI_BIN} --show-config --plugin {str(conf.sqlite_plugin)} --sqlite {str(conf.db_path)}:"
        sql = f'"SELECT option_key,option_value FROM uwsgi_options WHERE machine_id=\'{machine_id}\' ORDER BY sort_order_index"'
        process = Process(
            description="Device Manager",
            disabled=not conf.DEVICE_ENABLED,
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

    services.register_factory(
        context,
        DeviceProcess,
        device_process_factory,
        ping=device_ping,
        on_registry_close=device_close,
    )


def api_close():
    ...
    #logger.debug("api closed")


async def api_ping(api_data: tuple[APIProcess, ProcessMessages]):
    process, msgs = api_data
    # raise ServiceUnavailableError("dnsmasq down")
    return True


async def register_api_process(context: dict) -> None:
    """register api"""

    async def api_process_factory(svcs_container) -> tuple[APIProcess, ProcessMessages]:
        """FastAPI process-compose process"""

        conf = await svcs_container.aget(AppConfig)
        api_port = 9544
        # cmd = f"{conf.UV_BIN} run fastapi dev --port {api_port} src/pikesquares/app/main.py"
        cmd = f"{conf.UV_BIN} run uvicorn pikesquares.app.main:app --host 0.0.0.0 --port {api_port}"

        process_messages = ProcessMessages(
            title_start="!! api start title !!!",
            title_stop="abc",
        )
        process = Process(
            disabled=not conf.API_ENABLED,
            description="PikeSquares API",
            command=cmd,
            working_dir=Path().cwd(),
            availability=ProcessAvailability(),
            readiness_probe=ReadinessProbe(http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)),
        )
        return process, process_messages

    services.register_factory(
        context,
        APIProcess,
        api_process_factory,
        ping=api_ping,
        on_registry_close=api_close,
    )
