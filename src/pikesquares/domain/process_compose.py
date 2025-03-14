import json
import os
# import subprocess
from typing import Annotated
from pathlib import Path

import pydantic
import structlog
# from aiopath import AsyncPath
# from plumbum import local as pl_local
from plumbum import ProcessExecutionError
from pydantic_yaml import to_yaml_str

from pikesquares.conf import AppConfig
from pikesquares.domain.managed_services import ManagedServiceBase
from pikesquares.services.base import ServiceUnavailableError
from pikesquares.services import register_factory

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


class ProcessAvailability(pydantic.BaseModel):
    """
    restart other options: "on_failure", "exit_on_failure", "always", "no" (default)
    """
    restart: str = "yes"
    exit_on_end: str = "no"
    backoff_seconds: int = 2
    max_restarts: int = 5


class ProcessComposeProcess(pydantic.BaseModel):
    name: str
    description: str
    command: str
    is_elevated: bool = False
    working_dir: Annotated[pydantic.DirectoryPath, pydantic.Field()] | None = None
    # availability: ProcessAvailability
    disabled: bool = False
    is_daemon: bool = False
    depends_on: list["ProcessComposeProcess"] = []


class ProcessComposeConfig(pydantic.BaseModel):

    version: str = "0.1"
    is_strict: bool = True
    log_level: str = "debug"

    # log_configuration:
    #  fields_order: ["time", "level", "message"] # order of logging fields. The default is time, level, message
    #  disable_json: true                         # output as plain text. The default is false
    #  timestamp_format: "06-01-02 15:04:05.000"  # timestamp format. The default is RFC3339
    #  no_metadata: true                          # don't log process name and replica number
    #  add_timestamp: true                        # add timestamp to the logger. Default is false
    #  no_color: true                             # disable ANSII colors in the logger. Default is false
    #  flush_each_line: true                      # disable buffering and flush each line to the log file. Default is false

    processes: list[ProcessComposeProcess]


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
            # "PIKESQUARES_VERSION": self.conf.VERSION,
            # "PIKESQUARES_SCIE_BASE": str(self.conf.SCIE_BASE),
            # "PIKESQUARES_SCIE_LIFT_FILE": str(self.conf.SCIE_LIFT_FILE),
            # "UWSGI_BIN": str(self.conf.UWSGI_BIN),
            "PIKESQUARES_UV_BIN": str(self.uv_bin),
        }

        # "CADDY_BIN": str(self.conf.CADDY_BIN),
        # "DNSMASQ_BIN": str(self.conf.DNSMASQ_BIN),
        # "EASYRSA_BIN": str(self.conf.EASYRSA_BIN),

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

    """
    def attach(self) -> None:
        try:
            compl = subprocess.run(
                args=[
                  # str(self.conf.PROCESS_COMPOSE_BIN),
                  str(AsyncPath(os.environ.get("PIKESQUARES_PROCESS_COMPOSE_DIR")) / "process-compose"),
                  "attach",
                  "--unix-socket",
                  self.daemon_socket,
                ],
                cwd=str(self.conf.data_dir),
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as cperr:
            logger.error(f"failed to attach to server: {cperr.stderr.decode()}")
            return

        if compl.returncode != 0:
            logger.error("unable to attach server")

        logger.error(compl.stderr.decode())
        logger.debug(compl.stdout.decode())
    """

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
                            filter(lambda p: p.get("name") == "api", js)
                        )
                logger.debug(device_process)
                process_stats = ProcessComposeProcessStats(**device_process)
                if process_stats.IsRunning and process_stats.status == "Running":
                    return True
            except (IndexError, StopIteration):
                pass
        except ProcessExecutionError as exc:
            logger.error(exc)
            return False

        raise PCDeviceUnavailableError()
