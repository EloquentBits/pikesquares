import json
from pathlib import Path
import os
from typing import Annotated
from enum import Enum

import pydantic
import structlog
# from aiopath import AsyncPath
from plumbum import ProcessExecutionError
from pydantic_yaml import to_yaml_str

from pikesquares.conf import AppConfig, AppConfigError
from pikesquares.domain.managed_services import ManagedServiceBase
from pikesquares.domain.device import Device
from pikesquares.services.base import ServiceUnavailableError
from pikesquares import services
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
    """ process-compose process restart options """

    no = "no"  # default
    yes = "yes"
    on_failure = "on_failure"
    exit_on_failure = "exit_on_failure",
    always = "always"


class ProcessAvailability(pydantic.BaseModel):
    """ process-compose process availability options """

    restart: str = ProcessRestart.yes
    exit_on_end: str = "no"
    backoff_seconds: int = 2
    max_restarts: int = 5


class ReadinessProbeHttpGet(pydantic.BaseModel):
    """ process-compose readiness probe http get section """

    host: str = "127.0.0.1"
    scheme: str = "http"
    path: str = "/"
    port: int = 9544


class ReadinessProbe(pydantic.BaseModel):
    """ process-compose readiness probe section """

    http_get: ReadinessProbeHttpGet
    initial_delay_seconds: int = 5
    period_seconds: int = 10
    timeout_seconds: int = 5
    success_threshold: int = 1
    failure_threshold: int = 3


class ProcessComposeProcess(pydantic.BaseModel):
    """ process-compose process """

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
    """ process-compose process config (yaml) """

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

    def write_config_to_disk(self):
        self.daemon_config.write_text(
                to_yaml_str(self.config)
        )

    def reload(self):
        """ docket-compose project update """
        if not self.daemon_socket.exists():
            raise PCAPIUnavailableError()

        self.write_config_to_disk()
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

    def up(self) -> tuple[int, str, str]:
        # always write config to dist before starting
        self.write_config_to_disk()
        try:
            return self.cmd([
                    "up",
                    "--config",
                    str(self.daemon_config),
                    "--log-file",
                    str(self.daemon_log),
                    "--detached",
                    "--hide-disabled",
                    # "--tui",
                    # "false",
                ] + self.cmd_args,
                cmd_env=self.cmd_env,
            )

        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    def down(self) -> tuple[int, str, str]:
        if not self.daemon_socket.exists():
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
        if not self.daemon_socket.exists():
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
        if not self.daemon_socket.exists():
            raise PCAPIUnavailableError()

    def ping_api(self) -> bool:
        if not self.daemon_socket.exists():
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
                device_process = \
                    next(
                        filter(lambda p: p.get("name") in ["device", "api"], js)
                    )
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
def make_api_process(conf: AppConfig) -> ProcessComposeProcess:
    """ FastAPI process-compose process """
    api_port = 9544
    cmd = f"{conf.UV_BIN} run fastapi dev --port {api_port} src/pikesquares/app/main.py"
    return ProcessComposeProcess(
        description="PikeSquares FastAPI",
        command=cmd,
        working_dir=Path().cwd(),
        availability=ProcessAvailability(),
        readiness_probe=ReadinessProbe(
            http_get=ReadinessProbeHttpGet(path="/healthy", port=api_port)
        ),
    )


def make_device_process(dvc: Device, conf: AppConfig) -> ProcessComposeProcess:
    """ device process-compose process """
    sqlite3_plugin = conf.plugins_dir / "sqlite3_plugin.so"
    if not sqlite3_plugin.exists():
        raise AppConfigError(f"unable locate sqlite uWSGI plugin @ {str(sqlite3_plugin)}") from None

    sqlite3_db = conf.data_dir / "pikesquares.db"
    cmd = f"{conf.UWSGI_BIN} --plugin {str(sqlite3_plugin)} --sqlite {str(sqlite3_db)}:"
    sql = f'"SELECT option_key,option_value FROM uwsgi_options WHERE device_id=\'{dvc.id}\' ORDER BY sort_order_index"'
    return ProcessComposeProcess(
        description="PikeSquares Server",
        command="".join([cmd, sql]),
        working_dir=Path().cwd(),
        availability=ProcessAvailability(),
        # readiness_probe=ReadinessProbe(
            #    http_get=ReadinessProbeHttpGet()
        # ),
    )


def register_process_compose(context: dict, conf: AppConfig) -> None:
    """ process-compose factory"""

    device = context.get("device")
    if not device:
        raise AppConfigError("no device found in context")

    pc_config = ProcessComposeConfig(
        processes={
            "api": make_api_process(conf),
            "device": make_device_process(device, conf),
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
