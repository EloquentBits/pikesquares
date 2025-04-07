import errno
import grp
import json
import os
import pwd
import socket
import traceback
import uuid
from datetime import (
    UTC,
    datetime,
)
from pathlib import Path

# from typing import Any

import zmq
import zmq.asyncio
import pydantic
import structlog
from aiopath import AsyncPath
from sqlalchemy import (
    JSON,
    DateTime,
    func,
)
from sqlmodel import (
    # select,
    # Column,
    Field,
    # Integer,
    # String,
    # ForeignKey,
    # Relationship,
    SQLModel,
)

from pikesquares import __app_name__, __version__
from pikesquares.conf import AppConfigError
from pikesquares.exceptions import (
    ServiceUnavailableError,
    StatsReadError,
)

logger = structlog.getLogger()


class TimeStampedBase(SQLModel):

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "onupdate": func.now(),
            "server_default": func.now(),
        },
    )


"""
https://github.com/fastapi/sqlmodel/discussions/906
:w

class Customer(TypedDict):
    name: Annotated[str, Field(description="Name")]
    tel: Annotated[NotRequired[str | None], Field(description="Tel")] = None

class Factory(SQLModel):
    customers: Annotated[list[Customer], Field(sa_type=JSON, description="Customer list")] = []

"""


class ServiceBase(TimeStampedBase, SQLModel):
    """Base SQL model class."""

    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4()),
        max_length=36,
    )
    run_as_uid: str = Field(default="root")
    run_as_gid: str = Field(default="root")
    service_id: str = Field(default=None, unique=True)
    uwsgi_plugins: str | None = Field(default=None, max_length=255)
    data_dir: str = Field(default="/var/lib/pikesquares", max_length=255)
    log_dir: str = Field(default="/var/log/pikesquares", max_length=255)
    config_dir: str = Field(default="/etc/pikesquares", max_length=255)
    run_dir: str = Field(default="/var/run/pikesquares", max_length=255)

    cert_name: str | None = "_wildcard_pikesquares_dev"

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    @property
    def handler_name(self) -> str:
        return self.__class__.__name__

    def __repr__(self):
        return f'<{self.handler_name} id="{self.id}" service_id="{self.service_id}">'

    def __str__(self):
        return self.__repr__()

    # def model_post_init(self, __context: Any) -> None:
    #    uwsgi_config = self.write_uwsgi_config()
    #    logger.debug(f"wrote config to file: {uwsgi_config}")

    @pydantic.computed_field
    @property
    def stats_address(self) -> Path:
        """uWSGI Stats Server socket address"""
        return Path(self.run_dir) / f"{self.service_id}-stats.sock"

    @pydantic.computed_field
    @property
    def socket_address(self) -> Path:
        return Path(self.run_dir) / f"{self.service_id}.sock"

    @pydantic.computed_field
    @property
    def notify_socket(self) -> Path:
        return Path(self.run_dir) / f"{self.service_id}-notify.sock"

    @pydantic.computed_field
    @property
    def touch_reload_file(self) -> Path:
        return self.service_config

    @pydantic.computed_field
    @property
    def pid_file(self) -> Path:
        return Path(self.run_dir) / f"{self.service_id}.pid"

    @pydantic.computed_field
    @property
    def log_file(self) -> Path:
        return Path(self.log_dir) / f"{self.service_id}.log"

    @pydantic.computed_field
    @property
    def fifo_file(self) -> Path:
        return Path(self.run_dir) / f"{self.service_id}-master-fifo"

    @pydantic.computed_field
    @property
    def pki_dir(self) -> Path:
        return Path(self.data_dir) / "pki"

    @pydantic.computed_field
    @property
    def plugins_dir(self) -> Path:
        return Path(self.data_dir) / "plugins"

    @pydantic.computed_field(repr=False)
    @property
    def certificate(self) -> Path:
        return Path(self.pki_dir) / "issued" / f"{self.cert_name}.crt"

    @pydantic.computed_field(repr=False)
    @property
    def certificate_key(self) -> Path:
        return Path(self.pki_dir) / "private" / f"{self.cert_name}.key"

    @pydantic.computed_field(repr=False)
    @property
    def certificate_ca(self) -> Path:
        return Path(self.pki_dir) / "ca.crt"

    @pydantic.computed_field
    @property
    def spooler_dir(self) -> Path:
        return Path(self.data_dir) / "spooler"

    def write_uwsgi_config(self) -> Path:
        return self.uwsgi_config_section_class(self).as_configuration().tofile(self.service_config)

    def get_uwsgi_config(self) -> str:
        return self.uwsgi_config_section_class(self).as_configuration()

    @classmethod
    async def read_machine_id(cls) -> str:
        machine_id = await AsyncPath("/var/lib/dbus/machine-id").read_text(encoding="utf-8")
        return machine_id.strip()

    def make_system_file(
        self,
        newfile: Path | str,
        owner_username: str = "root",
        owner_groupname: str = "pikesquares",
        file_mode: int = 0o664,
    ) -> Path:
        if isinstance(newfile, str):
            newfile = Path(newfile)

        if newfile.exists():
            return newfile

        newfile.touch(mode=file_mode, exist_ok=True)
        try:
            owner_uid = pwd.getpwnam(owner_username)[2]
        except KeyError:
            raise AppConfigError(f"unable locate user: {owner_username}") from None

        try:
            owner_gid = grp.getgrnam(owner_groupname)[2]
        except KeyError:
            raise AppConfigError(f"unable locate group: {owner_groupname}") from None

        os.chown(newfile, owner_uid, owner_gid)

        return newfile

    async def device_zeromq_monitor_create_instance(self, device_zeromq_monitor_address: str) -> None:
        ctx = zmq.asyncio.Context()
        # zmq_socket = zmq.asyncio.Socket(zmq_context, zmq.PUSH)
        sock = ctx.socket(zmq.PUSH)
        sock.connect(f"tcp://{device_zeromq_monitor_address}")
        uwsgi_config = self.get_uwsgi_config()
        await sock.send_multipart(
            [
                b"touch",
                f"{self.service_id}.ini".encode(),
                uwsgi_config.format(do_print=True).encode(),
            ]
        )

    async def device_zeromq_monitor_restart_instance(self, device_zeromq_monitor_address: str) -> None:
        ctx = zmq.asyncio.Context()
        # zmq_socket = zmq.asyncio.Socket(zmq_context, zmq.PUSH)
        sock = ctx.socket(zmq.PUSH)
        sock.connect(f"tcp://{device_zeromq_monitor_address}")
        uwsgi_config = self.get_uwsgi_config()
        await sock.send_multipart(
            [
                b"touch",
                f"{self.service_id}.ini".encode(),
                uwsgi_config.format(do_print=True).encode(),
            ]
        )

    async def device_zeromq_monitor_destroy_instance(self, device_zeromq_monitor_address: str) -> None:
        ctx = zmq.asyncio.Context()
        # zmq_socket = zmq.asyncio.Socket(zmq_context, zmq.PUSH)
        sock = ctx.socket(zmq.PUSH)
        sock.connect(f"tcp://{device_zeromq_monitor_address}")
        await sock.send_multipart(
            [
                b"destroy",
                f"{self.service_id}.ini".encode(),
            ]
        )

    @classmethod
    def read_stats(cls, stats_address: Path):
        """
        read from uWSGI Stats Server socket
        """
        if not all([stats_address.exists(), stats_address.is_socket()]):
            raise StatsReadError(f"unable to read stats from {(stats_address)}")

        def unix_addr(arg):
            sfamily = socket.AF_UNIX
            addr = arg
            return sfamily, addr, socket.gethostname()

        js = ""
        sfamily, addr, _ = unix_addr(stats_address)
        try:
            s = None
            s = socket.socket(sfamily, socket.SOCK_STREAM)
            s.connect(str(addr))
            while True:
                data = s.recv(4096)
                if len(data) < 1:
                    break
                js += data.decode("utf8", "ignore")
            if s:
                s.close()
        except ConnectionRefusedError as e:
            raise StatsReadError(f"Connection refused @ {(stats_address)}")
        except FileNotFoundError as e:
            raise StatsReadError(f"Socket not available @ {(stats_address)}")
        except IOError as e:
            if e.errno != errno.EINTR:
                # uwsgi.log(f"socket @ {addr} not available")
                pass
        except Exception:
            logger.error(traceback.format_exc())
        else:
            try:
                return json.loads(js)
            except json.JSONDecodeError:
                logger.error(traceback.format_exc())
                logger.info(js)

    def write_master_fifo(self, command: str) -> None:
        """
        Write command to master fifo named pipe

        '0' to '9' - set the fifo slot (see below)
        '+' - increase the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
        '-' - decrease the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
        'B' - ask Emperor for reinforcement (broodlord mode, requires uWSGI >= 2.0.7)
        'C' - set cheap mode
        'c' - trigger chain reload
        'E' - trigger an Emperor rescan
        'f' - re-fork the master (dangerous, but very powerful)
        'l' - reopen log file (need -log-master and -logto/-logto2)
        'L' - trigger log rotation (need -log-master and -logto/-logto2)
        'p' - pause/resume the instance
        'P' - update pidfiles (can be useful after master re-fork)
        'Q' - brutally shutdown the instance
        'q' - gracefully shutdown the instance
        'R' - send brutal reload
        'r' - send graceful reload
        'S' - block/unblock subscriptions
        's' - print stats in the logs
        'W' - brutally reload workers
        'w' - gracefully reload workers
        """

        if command not in {"r", "q", "s"}:
            logger.warning(f"unknown master fifo command '{command}'")
            return

        if not all(
            [
                self.fifo_file,
                self.fifo_file.exists(),
            ]
        ):
            logger.warning(f"invalid fifo file @ {self.fifo_file}")
            return

        with open(str(self.fifo_file), "w") as master_fifo:
            master_fifo.write(command)
            logger.info(f"[pikesquares-services] : sent command [{command}] to master fifo")

    def ping(self) -> None:
        if not self.get_service_status() == "running":
            raise ServiceUnavailableError()

    def get_service_status(self) -> str | None:
        """
        read stats socket
        """
        if self.stats_address.exists() and self.stats_address.is_socket():
            return "running" if ServiceBase.read_stats(self.stats_address) else "stopped"

    def startup_log(self, show_config_start_marker: str, show_config_end_marker: str) -> tuple[list, list]:
        """
        read the output of `show-config` option from the service log
        """
        with open(str(self.log_file)) as f:
            log_lines = f.readlines()
            start_index = max(idx for idx, val in enumerate(log_lines) if val == show_config_start_marker)
            end_index = max(idx for idx, val in enumerate(log_lines) if val == show_config_end_marker)
            # print(f"{start_index} {end_index}")
            latest_running_config = log_lines[start_index : end_index + 1]
            latest_startup_log = log_lines[end_index + 1 :]
        return latest_running_config, latest_startup_log

    # @pydantic.computed_field
    # def caddy(self) -> Path | None:
    #    try:
    #        return self.caddy_dir / "caddy"
    #    except TypeError:
    #        pass

    # @pydantic.computed_field
    # def caddy_dir(self) -> Path | None:
    #    if self.CADDY_DIR and Path(self.CADDY_DIR).exists():
    #        return Path(self.CADDY_DIR)
