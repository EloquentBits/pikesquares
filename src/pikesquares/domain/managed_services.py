from pathlib import Path
from typing import Annotated

import pydantic
import structlog
from plumbum import ProcessExecutionError
from plumbum import local as pl_local

#from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlmodel import (
    Field,
    Relationship,
)

from pikesquares.domain.base import ServiceBase

logger = structlog.get_logger()


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

    #attached_daemons_dir

    #for_legion=False,
    #broken_counter=3,
    #pidfile=pidfile,
    #control=False,
    #daemonize=True,
    #touch_reload="/etc/pikesquares/redis.conf",
    #signal_stop=15,
    #signal_reload=15,
    #honour_stdin=0,
    #uid="pikesquares",
    #gid="pikesquares",
    #new_pid_ns="false",
    #change_dir="/var/lib/pikesquares/redis",

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


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

