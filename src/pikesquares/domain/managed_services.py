from typing import NewType
from pathlib import Path
from string import Template
from typing import Annotated

from pluggy import PluginManager, HookspecMarker, HookimplMarker
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


AttachedDaemonPluginManager = NewType("AttachedDaemonPluginManager", PluginManager)

hook_spec = HookspecMarker("attached-daemon" )
hook_impl = HookimplMarker("attached-daemon" )

"""
https://www.postgresql.org/docs/current/reference-server.html

smart-attach-daemon = %(pg)/postmaster.pid /usr/lib/postgresql/9.6/bin/postgres -D %(pg)

; backup
env = PGPASSWORD=XXX
cron = 59 3 -1 -1 -1  pg_dump -U ZZZ YYY | bzip2 -9 > $(HOME)/backup/YYY_`date +"%%d"`.sql.bz2
"""


class PostgresAttachedDaemonPlugin:

    def __init__(
        self,
        daemon_service: "AttachedDaemon",
        bind_ip: str,
        bind_port: int | None = None
    ):
        self.daemon_service = daemon_service
        self.bind_ip = bind_ip
        self.bind_port = bind_port or 5432

    def get_daemon_bin(self) -> Path:
        return Path("/usr/lib/postgresql/16/bin/postgres")


    @hook_impl
    def collect_command_arguments(self) -> dict:
        cmd = Template(
            "$bin -D $dir -h $bind_ip -p $bind_port -k $rundir"
        ).substitute({
            "bin" : str(self.get_daemon_bin()),
            "bind_port": self.bind_port,
            "bind_ip": self.bind_ip,
            "dir": str(self.daemon_service.daemon_data_dir),
            "rundir": str(self.daemon_service.run_dir),
            #"logfile": str(Path(self.daemon_service.log_dir) / f"{self.daemon_service.name}-server-{self.daemon_service.service_id}.log"),
            #"pidfile": str(self.daemon_service.pid_file),
        })
        logger.debug(cmd)
        #import ipdb;ipdb.set_trace()

        return {
            "command": cmd,
            "for_legion": self.daemon_service.for_legion,
            "broken_counter": self.daemon_service.broken_counter,
            "pidfile": self.daemon_service.pid_file,
            "control": self.daemon_service.control,
            "daemonize": self.daemon_service.daemonize,
            "touch_reload": str(self.daemon_service.touch_reload_file),
            "signal_stop": self.daemon_service.signal_stop,
            "signal_reload": self.daemon_service.signal_reload,
            "honour_stdin": bool(self.daemon_service.honour_stdin),
            "uid": self.daemon_service.run_as_uid,
            "gid": self.daemon_service.run_as_gid,
            "new_pid_ns": self.daemon_service.new_pid_ns,
            "change_dir": str(self.daemon_service.daemon_data_dir),
        }

    @hook_impl
    def stop(self) -> bool:
        """
           stop postgres
        """
        ...


class RedisAttachedDaemonPlugin:

    def __init__(
        self,
        daemon_service: "AttachedDaemon",
        bind_ip: str,
        bind_port: int | None = None
    ):
        self.daemon_service = daemon_service
        self.bind_ip = bind_ip
        self.bind_port = bind_port or 6379

    def get_daemon_bin(self) -> Path:
        return Path("/usr/bin/redis-server")

    def get_daemon_cli_bin(self) -> Path:
        return Path("/usr/bin/redis-cli")

    # get data dir
    #   redis-cli config get dir

    @hook_impl
    def collect_command_arguments(self) -> dict:
        cmd = Template(
            "$bin --pidfile $pidfile --logfile $logfile --dir $dir --bind $bind_ip --port $bind_port --daemonize no --protected-mode no"
        ).substitute({
            "bin" : str(self.get_daemon_bin()),
            "bind_port": self.bind_port,
            "bind_ip": self.bind_ip,
            "dir": str(self.daemon_service.daemon_data_dir),
            "logfile": str(Path(self.daemon_service.log_dir) / f"{self.daemon_service.name}-server-{self.daemon_service.service_id}.log"),
            "pidfile": str(self.daemon_service.pid_file),
        })
        logger.debug(cmd)

        return {
            "command": cmd,
            "for_legion": self.daemon_service.for_legion,
            "broken_counter": self.daemon_service.broken_counter,
            "pidfile": self.daemon_service.pid_file,
            "control": self.daemon_service.control,
            "daemonize": self.daemon_service.daemonize,
            "touch_reload": str(self.daemon_service.touch_reload_file),
            "signal_stop": self.daemon_service.signal_stop,
            "signal_reload": self.daemon_service.signal_reload,
            "honour_stdin": bool(self.daemon_service.honour_stdin),
            "uid": self.daemon_service.run_as_uid,
            "gid": self.daemon_service.run_as_gid,
            "new_pid_ns": self.daemon_service.new_pid_ns,
            "change_dir": str(self.daemon_service.daemon_data_dir),
        }

    @hook_impl
    def ping(self) -> bool:
        """
            ping redis
        """
        cmd_args = ["-h", self.bind_ip, "-p", self.bind_port, "--raw", "incr", "ping"]
        logger.info(cmd_args)
        try:
            with pl_local.cwd(self.daemon_service.daemon_data_dir):
                retcode, stdout, stderr = pl_local[str(self.get_daemon_cli_bin())].run(cmd_args)
                if int(retcode) != 0:
                    logger.debug(f"{retcode=}")
                    logger.debug(f"{stdout=}")
                    logger.debug(f"{stderr=}")
                    return False
                else:
                    return stdout.strip().isdigit()
        except ProcessExecutionError:
            raise

    @hook_impl
    def stop(self) -> bool:
        """
           stop redis
        """
        cmd_args = ["-h", self.bind_ip, "-p", self.bind_port, "shutdown"]
        if not Path(self.daemon_service.daemon_data_dir).exists():
            logger.info(f"{self.daemon_service.service_id} data directory missing")
            return False
        try:
            with pl_local.cwd(self.daemon_service.daemon_data_dir):
                retcode, stdout, stderr = pl_local[
                    str(self.get_daemon_cli_bin())
                ].run(cmd_args)

                if int(retcode) != 0:
                    logger.debug(f"{retcode=}")
                    logger.debug(f"{stdout=}")
                    logger.debug(f"{stderr=}")
                    return False
                else:
                    return stdout.strip().isdigit()
        except ProcessExecutionError as exc:
            raise exc



class SimpleSocketAttachedDaemonPlugin:

    def __init__(
        self,
        daemon_service: "AttachedDaemon",
        bind_ip: str,
        bind_port: int | None = None
    ):
        self.daemon_service = daemon_service
        self.bind_ip = bind_ip
        self.bind_port = bind_port or 6379

    def get_daemon_bin(self) -> Path:
        return Path("/usr/bin/redis-server")

    def get_daemon_cli_bin(self) -> Path:
        return Path("/usr/bin/redis-cli")

    @hook_impl
    def collect_command_arguments(self) -> dict:
        cmd = Template(
            "$bin --pidfile $pidfile --logfile $logfile --dir $dir --bind $bind_ip --port $bind_port --daemonize no --protected-mode no"
        ).substitute({
            "bin" : str(self.get_daemon_bin()),
            "bind_port": self.bind_port,
            "bind_ip": self.bind_ip,
            "dir": str(self.daemon_service.daemon_data_dir),
            "logfile": str(Path(self.daemon_service.log_dir) / f"{self.daemon_service.name}-server-{self.daemon_service.service_id}.log"),
            "pidfile": str(self.daemon_service.pid_file),
        })
        logger.debug(cmd)

        return {
            "command": cmd,
            "for_legion": self.daemon_service.for_legion,
            "broken_counter": self.daemon_service.broken_counter,
            "pidfile": self.daemon_service.pid_file,
            "control": self.daemon_service.control,
            "daemonize": self.daemon_service.daemonize,
            #"touch_reload": str(self.daemon_service.touch_reload_file),
            "signal_stop": self.daemon_service.signal_stop,
            "signal_reload": self.daemon_service.signal_reload,
            "honour_stdin": bool(self.daemon_service.honour_stdin),
            "uid": self.daemon_service.run_as_uid,
            "gid": self.daemon_service.run_as_gid,
            "new_pid_ns": self.daemon_service.new_pid_ns,
            "change_dir": str(self.daemon_service.daemon_data_dir),
        }

    @hook_impl
    def ping(self) -> bool:
        """
            ping redis
        """
        cmd_args = ["-h", self.bind_ip, "-p", self.bind_port, "--raw", "incr", "ping"]
        try:
            with pl_local.cwd(self.daemon_service.daemon_data_dir):
                retcode, stdout, stderr = pl_local[str(self.get_daemon_cli_bin())].run(cmd_args)
                if int(retcode) != 0:
                    logger.debug(f"{retcode=}")
                    logger.debug(f"{stdout=}")
                    logger.debug(f"{stderr=}")
                    return False
                else:
                    return stdout.strip().isdigit()
        except ProcessExecutionError:
            raise

    @hook_impl
    def stop(self) -> bool:
        """
           stop socket server
        """
        ...



class AttachedDaemonHookSpec:
    """
    Attached Daemon Hook Specification
    """

    @hook_spec(firstresult=True)
    def collect_command_arguments(self) -> None:
        ...

    @hook_spec(firstresult=True)
    def ping(self) -> bool:
        ...

    @hook_spec(firstresult=True)
    def stop(self) -> bool:
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

    create_data_dir: bool = Field(default=True)

    @property
    def daemon_data_dir(self) -> Path:
        daemon_dir = Path(self.data_dir) / "attached-daemons" / self.service_id
        #if not daemon_dir.exists() and self.create_data_dir:
        #    daemon_dir.mkdir(parents=True, exist_ok=True)
        return daemon_dir

    @property
    def touch_reload_file(self) -> Path | None:
        return self.daemon_data_dir / "touch-to-reload"


class ManagedServiceBase(pydantic.BaseModel):

    daemon_name: str
    daemon_bin: Annotated[pydantic.FilePath, pydantic.Field()]
    daemon_config: Annotated[pydantic.FilePath, pydantic.Field()] | None = None
    data_dir: Annotated[pydantic.DirectoryPath, pydantic.Field()] | None = None
    run_dir: Annotated[pydantic.DirectoryPath, pydantic.Field()] | None = None
    log_dir: Annotated[pydantic.DirectoryPath, pydantic.Field()] | None = None

    class Config:
        arbitrary_types_allowed = True

    def __repr__(self) -> str:
        return f"<{self.daemon_name} daemon_bin={self.daemon_bin}>"

    def __str__(self) -> str:
        return f"{self.daemon_name} @ {self.daemon_bin}"

    @property
    def daemon_socket(self) -> Path:
        return Path(self.run_dir) / f"{self.daemon_name}.sock"

    @property
    def daemon_log(self) -> Path:
        return Path(self.log_dir) / f"{self.daemon_name}.log"

    def cmd(
        self,
        cmd_args: list[str],
        chdir: Path | None = None,
        cmd_env: dict[str, str] | None = None,
        # run_as_user: str = "pikesquares",
    ) -> tuple[int | None, str | None, str | None]:

        if not cmd_args:
            raise Exception(f"no args provided for e {self.daemon_name} command")

        #print(cmd_args)

        try:
            if cmd_env:
                pl_local.env.update(cmd_env)
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
