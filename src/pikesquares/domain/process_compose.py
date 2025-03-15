import json
import os
from typing import Annotated
from enum import Enum

import pydantic
import structlog
# from aiopath import AsyncPath
from plumbum import ProcessExecutionError
from pydantic_yaml import to_yaml_str

from pikesquares.domain.managed_services import ManagedServiceBase
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

    def up(self) -> tuple[int, str, str]:
        cmd_args = [
            "up",
            "--config",
            str(self.daemon_config),
            "--log-file",
            str(self.daemon_log),
            "--detached",
            "--hide-disabled",
            # "--tui",
            # "false",
            "--unix-socket",
            str(self.daemon_socket),

        ]
        cmd_env = {
            # TODO use shellingham library
            "COMPOSE_SHELL": os.environ.get("SHELL"),
        }

        try:
            return self.cmd(cmd_args, cmd_env=cmd_env)
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    def down(self) -> tuple[int, str, str]:
        if not self.daemon_socket.exists():
            raise PCAPIUnavailableError()

        cmd_args = ["down", "--unix-socket", str(self.daemon_socket)]
        try:
            return self.cmd(cmd_args)
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    def attach(self) -> tuple[int, str, str]:
        if not self.daemon_socket.exists():
            raise PCAPIUnavailableError()

        cmd_args = ["attach", "--unix-socket", str(self.daemon_socket)]
        try:
            return self.cmd(cmd_args)
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
                "--use-uds",
                "--unix-socket",
                self.daemon_socket,
                "--output",
                "json",
            ]
            retcode, stdout, stderr = self.cmd(cmd_args)
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
