from pathlib import Path
from string import Template
from typing import Annotated

import pluggy
import pydantic
import structlog
from plumbum import ProcessExecutionError
from plumbum import local as pl_local
from sqlmodel import (
    Field,
    Relationship,
)

from pikesquares.domain.base import ServiceBase

logger = structlog.get_logger()

hook_spec = pluggy.HookspecMarker("managed_daemon" )
hook_impl = pluggy.HookimplMarker("managed_daemon" )


class RedisAttachedDaemon:

    def get_daemon_bin(self):
        return "/usr/bin/redis-server"

    def compose_command(
        self,
        daemon_service: "AttachedDaemon",
        bind_ip: str,
        bind_port: int = 6379,
    ) -> str:
        return Template(
            "$bin --pidfile $pidfile --logfile $logfile --dir $dir --bind $bind_ip --port $bind_port --daemonize no --protected-mode no"
        ).substitute({
            "bin" : self.get_daemon_bin(),
            "bind_port": bind_port,
            "bind_ip": bind_ip,
            "dir": str(daemon_service.daemon_data_dir),
            "logfile": str(Path(daemon_service.log_dir) / f"{daemon_service.name}-server-{daemon_service.service_id}.log"),
            "pidfile": str(daemon_service.pid_file),
        })


    @hook_impl
    def collect_command_arguments(
        self,
        daemon_service: "AttachedDaemon",
        bind_ip: str,
        bind_port: int = 6379,
    ) -> dict:
        return {
            "command": self.compose_command(daemon_service, bind_ip, bind_port=bind_port),
            "for_legion": daemon_service.for_legion,
            "broken_counter": daemon_service.broken_counter,
            "pidfile": daemon_service.pid_file,
            "control": daemon_service.control,
            "daemonize": daemon_service.daemonize,
            "touch_reload": str(daemon_service.touch_reload_file),
            "signal_stop": daemon_service.signal_stop,
            "signal_reload": daemon_service.signal_reload,
            "honour_stdin": bool(daemon_service.honour_stdin),
            "uid": daemon_service.run_as_uid,
            "gid": daemon_service.run_as_gid,
            "new_pid_ns": daemon_service.new_pid_ns,
            "change_dir": str(daemon_service.daemon_data_dir),
        }

    @hook_impl
    def ping(
        self,
        cmd_bin: str,
        daemon_service: "AttachedDaemon",
        bind_ip: str,
        bind_port: str,
             ) -> bool:
        """
            ping redis
        """
        cmd_args = ["-h", bind_ip, "-p", bind_port, "--raw", "incr", "ping"]
        try:
            with pl_local.cwd(daemon_service.daemon_data_dir):
                retcode, stdout, stderr = pl_local[cmd_bin].run(cmd_args)
                if int(retcode) != 0:
                    logger.debug(f"{retcode=}")
                    logger.debug(f"{stdout=}")
                    logger.debug(f"{stderr=}")
                    return False
                else:
                    return stdout.strip().isdigit()
        except ProcessExecutionError:
            raise



class AttachedDaemonHookSpec:
    """
    Attached Daemon Hook Specification
    """

    @hook_spec
    def collect_command_arguments(
        self,
        daemon_service: "AttachedDaemon",
        bind_ip: str,
        bind_port: int,
    ) -> None:
        ...


    @hook_spec
    def ping(
        self,
        cmd_bin: str,
        daemon_service: "AttachedDaemon",
        bind_ip: str,
        bind_port: int,
    ) -> bool:
        ...


class AttachedDaemon(ServiceBase, table=True):
    """uWSGI Attached Daemons model class."""

    __tablename__ = "attached_daemons"

    name: str = Field(max_length=32)
    for_legion: bool = Field(default=False)
    broken_counter: int = Field(default=3)
    #pidfile: str | None = Field(max_length=255)
    control: bool = Field(default=False)
    daemonize: bool = Field(default=True)
    #touch_reload: str | None = Field(max_length=255)
    signal_stop: int = Field(default=15)
    signal_reload: int = Field(default=15)
    honour_stdin: int = Field(default=0)
    new_pid_ns: str = Field(default="false")
    #change_dir: str = Field(max_length=255)

    project_id: str | None = Field(default=None, foreign_key="projects.id")
    project: "Project" = Relationship(back_populates="attached_daemons")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    @property
    def daemon_data_dir(self) -> Path:
        daemon_dir = Path(self.data_dir) / "attached-daemons" / self.service_id
        if not daemon_dir.exists():
            daemon_dir.mkdir(parents=True, exist_ok=True)
        return daemon_dir

    @property
    def touch_reload_file(self) -> Path:
        return self.daemon_data_dir

    def compile_command_args(
        self,
        bind_ip: str,
        bind_port: int | None = None,
    ) -> dict:

        pm = pluggy.PluginManager("managed_daemon")
        pm.add_hookspecs(AttachedDaemonHookSpec)
        pm.register(RedisAttachedDaemon())

        cmd_args = pm.hook.collect_command_arguments(
            daemon_service=self,
            bind_ip=bind_ip,
            bind_port=bind_port,
        )
        logger.debug(f"{self.name} command args=> {cmd_args}")
        # FIXME
        # why is this a list?
        if cmd_args and isinstance(cmd_args, list):
            return cmd_args[0]
        return cmd_args


class ManagedServiceBase(pydantic.BaseModel):

    daemon_name: str
    daemon_bin: Annotated[Path, pydantic.Field()]
    daemon_log: Annotated[Path, pydantic.Field()] | None = None
    daemon_config: Annotated[Path, pydantic.Field()] | None = None
    daemon_socket: Annotated[Path, pydantic.Field()] | None = None

    data_dir: Annotated[pydantic.DirectoryPath, pydantic.Field()] | None = None

    class Config:
        arbitrary_types_allowed = True

    def __repr__(self) -> str:
        return f"<{self.daemon_name} daemon_bin={self.daemon_bin}>"

    def __str__(self) -> str:
        return f"{self.daemon_name} @ {self.daemon_bin}"

    def cmd(
        self,
        cmd_args: list[str],
        chdir: Path | None = None,
        cmd_env: dict[str, str] | None = None,
        # run_as_user: str = "pikesquares",
    ) -> tuple[int | None, str | None, str | None]:

        if not cmd_args:
            raise Exception(f"no args provided for e {self.daemon_name} command")

        try:
            if cmd_env:
                pl_local.env.update(cmd_env)
                logger.debug(f"{cmd_env=}")

            # with pl_local.as_user(run_as_user):
            with pl_local.cwd(chdir or self.data_dir):
                retcode, stdout, stderr = pl_local[str(self.daemon_bin)].run(cmd_args, **{"env": cmd_env})
                if int(retcode) != 0:
                    logger.debug(f"{retcode=}")
                    logger.debug(f"{stdout=}")
                    logger.debug(f"{stderr=}")
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
            # raise UvCommandExecutionError(
            #        f"uv cmd [{' '.join(cmd_args)}] failed.\n{exc.stderr}"
            # )

class Redis(ManagedServiceBase):


    cmd_args: list[str] = []
    cmd_env: dict[str, str] = {}

