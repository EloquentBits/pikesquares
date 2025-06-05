import grp
from asyncio import sleep
import json
import os
from enum import Enum
from pathlib import Path
from typing import Annotated, NewType

import pydantic
import structlog
from aiopath import AsyncPath
from plumbum import ProcessExecutionError
from pydantic_yaml import to_yaml_str

from pikesquares import services
from pikesquares.conf import AppConfig, AppConfigError
#from pikesquares.domain.device import Device
from pikesquares.domain.managed_services import ManagedServiceBase

# from pikesquares.service_layer.uow import UnitOfWork

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
        logger.info(f"new config. reloading process compose")
        try:
            self.cmd_args.insert(0, "project")
            self.cmd_args.insert(1, "update")
            self.cmd_args.insert(2, "--config")
            self.cmd_args.insert(3, str(self.daemon_config))
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

        # Set the current numeric umask and return the previous umask.
        old_umask = os.umask(0o002)
        os.setgid(grp.getgrnam("pikesquares")[2])
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
        finally:
            os.umask(old_umask)

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


APIProcess = NewType("APIProcess", Process)
DeviceProcess = NewType("DeviceProcess", Process)
# DeviceProcessMessages = NewType("DeviceProcessMessages", ProcessMessages)
DNSMASQProcess = NewType("DNSMASQProcess", Process)


async def process_compose_ping(pc: ProcessCompose):
    # raise ServiceUnavailableError("process compose down")
    return True


async def register_process_compose(context: dict) -> None:
    """process-compose factory"""

    async def process_compose_factory(svcs_container) -> ProcessCompose:
        from pikesquares.domain.caddy import CaddyProcess

        # uow = await services.aget(context, UnitOfWork)
        conf = await svcs_container.aget(AppConfig)
        if conf.UV_BIN and not await AsyncPath(conf.UV_BIN).exists():
            raise AppConfigError(f"unable locate uv binary @ {conf.UV_BIN}") from None

        if conf.UWSGI_BIN and not await AsyncPath(conf.UWSGI_BIN).exists():
            raise AppConfigError(f"unable locate uWSGI binary @ {conf.UWSGI_BIN}") from None

        device_process, device_messages = await svcs_container.aget(DeviceProcess)
        caddy_process, caddy_messages = await svcs_container.aget(CaddyProcess)
        dnsmasq_process, dnsmasq_messages = await svcs_container.aget(DNSMASQProcess)
        api_process, api_messages = await svcs_container.aget(APIProcess)

        pc_config = Config(
            processes={
                #"api": api_process,
                "device": device_process,
                #"caddy": caddy_process,
                #"dnsmasq": dnsmasq_process,
            },
            custom_messages={
                #"api": api_messages,
                "device": device_messages,
                #"caddy": caddy_messages,
                #"dnsmasq": dnsmasq_messages,
            },
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


def dnsmasq_close():
    ...
    #logger.debug("dnsmasq closed")


async def dnsmasq_ping(dnsmasq_data: tuple[DNSMASQProcess, ProcessMessages]):
    process, msgs = dnsmasq_data
    # raise ServiceUnavailableError("dnsmasq down")
    return True


async def register_dnsmasq_process(
    context: dict,
    port: int = 5353,
    addresses: list[str] = ["/pikesquares.local/192.168.34.3"],
    listen_address: str = "127.0.0.34",
) -> None:
    """register device"""

    async def dnsmasq_process_factory(svcs_container) -> tuple[DNSMASQProcess, ProcessMessages]:
        """dnsmasq process-compose process"""

        conf = await svcs_container.aget(AppConfig)

        if conf.DNSMASQ_BIN and not await AsyncPath(conf.DNSMASQ_BIN).exists():
            raise AppConfigError(f"unable locate dnsmasq binary @ {conf.DNSMASQ_BIN}") from None

        #--interface=incusbr0

        cmd = f"{conf.DNSMASQ_BIN} " \
            "--bind-interfaces " \
            "--conf-file=/dev/null " \
            "--keep-in-foreground " \
            "--log-queries " \
            f"--port {port} " \
            f"--listen-address {listen_address} " \
            "--no-resolv " \
            "-u pikesquares -g pikesquares" 



        for addr in addresses:
            cmd = cmd + f" --address {addr}"

        process_messages = ProcessMessages(
            title_start="!!! dnsmasq start title !!!",
            title_stop="abc",
        )
        process = Process(
            disabled=not conf.DNSMASQ_ENABLED,
            description="dns resolver",
            command=cmd,
            working_dir=conf.data_dir,
            availability=ProcessAvailability(),
            # readiness_probe=ReadinessProbe(
            #    http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
            # ),
        )
        return process, process_messages

    services.register_factory(
        context,
        DNSMASQProcess,
        dnsmasq_process_factory,
        ping=dnsmasq_ping,
        on_registry_close=dnsmasq_close,
    )


