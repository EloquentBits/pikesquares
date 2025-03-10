from typing import Any
from functools import cached_property
from pathlib import Path
import json
import os
import subprocess

import pydantic
import structlog
from aiopath import AsyncPath
from plumbum import local as pl_local
from plumbum import ProcessExecutionError
from sqlmodel import Field

from pikesquares.conf import AppConfig
from pikesquares.services.base import ServiceUnavailableError
from pikesquares.services import register_factory
from pikesquares.cli.console import console

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


class ProcessCompose(pydantic.BaseModel):

    conf: AppConfig | None = None

    class Config:
        arbitrary_types_allowed = True

    def __repr__(self) -> str:
        return "process-compose"

    def __str__(self) -> str:
        return self.__repr__()

    # @pydantic.computed_field
    async def get_socket_address(self) -> AsyncPath:
        return await AsyncPath(
            self.conf.run_dir) / "process-compose.sock"

    async def ping(self) -> None:
        sockaddr = AsyncPath(
            self.conf.run_dir) / "process-compose.sock"

        if not await sockaddr.exists():
            raise PCAPIUnavailableError()

    async def ping_api(self) -> bool:
        sockaddr = AsyncPath(
            self.conf.run_dir) / "process-compose.sock"

        if not await sockaddr.exists():
            raise PCAPIUnavailableError()

        try:
            cmd_args = [
                "process",
                "list",
                "--use-uds",
                "--unix-socket",
                str(await self.get_socket_address()),
                "--output",
                "json",
            ]
            retcode, stdout, stderr = await self.pc_cmd(cmd_args)
            js = json.loads(stdout)
            try:
                device_process = \
                        next(
                            filter(lambda p: p.get("name") == "Device", js)
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

    async def up(self) -> tuple[int, str, str]:
        sockaddr = AsyncPath(
            self.conf.run_dir) / "process-compose.sock"

        cmd_args = [
            "up",
            "--config",
            str(self.conf.PROCESS_COMPOSE_CONFIG),
            "--log-file",
            str(AsyncPath(self.conf.log_dir) / "process-compose.log"),
            "--detached",
            "--hide-disabled",
            # "--tui",
            # "false",
            "--unix-socket",
            str(sockaddr),

        ]
        logger.info("calling process-compose up")
        try:
            return await self.pc_cmd(cmd_args)
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    async def down(self) -> tuple[int, str, str]:
        sockaddr = AsyncPath(
            self.conf.run_dir) / "process-compose.sock"

        if not await sockaddr.exists():
            raise PCAPIUnavailableError()

        cmd_args = [
            "down",
            "--unix-socket",
            str(AsyncPath(self.conf.run_dir) / "process-compose.sock"),
        ]
        logger.info("calling process-compose down")
        try:
            return await self.pc_cmd(cmd_args)
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    async def attach(self) -> None:
        try:
            compl = subprocess.run(
                args=[
                  # str(self.conf.PROCESS_COMPOSE_BIN),
                  str(AsyncPath(os.environ.get("PIKESQUARES_PROCESS_COMPOSE_DIR")) / "process-compose"),
                  "attach",
                  "--unix-socket",
                  str(await self.get_socket_address()),
                ],
                cwd=str(await AsyncPath(self.conf.data_dir)),
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

    async def pc_cmd(
            self,
            cmd_args: list[str],
            # run_as_user: str = "pikesquares",
            cmd_env: dict | None = None,
            chdir: AsyncPath | None = None,
        ) -> tuple[int, str, str]:
        logger.info(f"[pikesquares] pc_cmd: {cmd_args=}")

        cmd_env = {
            # TODO use shellingham library
            "COMPOSE_SHELL": os.environ.get("SHELL"),
            "PIKESQUARES_VERSION": self.conf.VERSION,
            "PIKESQUARES_SCIE_BASE": str(self.conf.SCIE_BASE),
            "PIKESQUARES_SCIE_LIFT_FILE": str(self.conf.SCIE_LIFT_FILE),
            "UWSGI_BIN": str(self.conf.UWSGI_BIN),
            "LOG_DIR": self.conf.log_dir,
            "UV_BIN": str(self.conf.UV_BIN),
            "CADDY_BIN": str(self.conf.CADDY_BIN),
            "DNSMASQ_BIN": str(self.conf.DNSMASQ_BIN),
            # "EASYRSA_BIN": str(self.conf.EASYRSA_BIN),
            # "PIKESQUARES_PROCESS_COMPOSE_BIN": str(self.conf.PROCESS_COMPOSE_BIN),
        }

        logger.debug(cmd_env)
        logger.debug(cmd_args)

        try:
            if cmd_env:
                pl_local.env.update(cmd_env)
                logger.debug(f"{cmd_env=}")

            # with pl_local.as_user(run_as_user):
            with pl_local.cwd(chdir or self.conf.data_dir):
                pc = pl_local[str(self.conf.PROCESS_COMPOSE_BIN)]
                retcode, stdout, stderr = pc.run(
                    cmd_args,
                    **{"env": cmd_env}
                )
                logger.debug(f"[pikesquares] pc_cmd: {retcode=}")
                logger.debug(f"[pikesquares] pc_cmd: {stdout=}")
                logger.debug(f"[pikesquares] pc_cmd: {stderr=}")
                return retcode, stdout, stderr
        except ProcessExecutionError:
            raise
            # print(vars(exc))
            # {
            #    'message': None,
            #    'host': None,
            #    'argv': ['/home/pk/.local/bin/uv', 'run', 'manage.py', 'check'],
            #    'retcode': 1
            #    'stdout': '',
            #    'stderr': "warning: `VIRTUAL_ENV=/home/pk/dev/eqb/pikesquares/.venv` does not match the project environment path `.venv` and will be ignored\nSystemCheckError: System check identified some issues:\n\nERRORS:\n?: (caches.E001) You must define a 'default' cache in your CACHES setting.\n\nSystem check identified 1 issue (0 silenced).\n"
            # }
            # print(traceback.format_exc())
            #raise UvCommandExecutionError(
            #        f"uv cmd [{' '.join(cmd_args)}] failed.\n{exc.stderr}"
            #)


async def register_process_compose(
        context,
        conf: AppConfig,
    ):
    async def process_compose_factory() -> ProcessCompose:
        kwargs = {"conf": conf}
        return ProcessCompose(**kwargs)

    register_factory(
        context,
        ProcessCompose,
        process_compose_factory,
        # ping=lambda svc: await svc.ping(),
    )
