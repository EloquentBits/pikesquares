import json
import traceback
import socket
import errno
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, List

import pydantic
from pydantic.config import ConfigDict
from tinydb import TinyDB, Query
from uwsgiconf import uwsgi
import structlog
import sentry_sdk

from pikesquares import __version__, __app_name__
from pikesquares import conf
from pikesquares.presets import Section
from pikesquares.cli.console import console

logger = structlog.get_logger()

__all__ = (
    "BaseService",
)


class ServiceUnavailableError(Exception):
    pass


class StatsReadError(Exception):
    pass


class BaseService(pydantic.BaseModel, ABC):

    conf: conf.AppConfig
    db: TinyDB
    service_id: str
    # cache:str = "pikesquares-settings"
    parent_service_id: str | None = None
    cert_name: str = "_wildcard_pikesquares_dev"
    name: str = ""
    plugins: list = []
    tiny_db_table: str = ""
    config_section_class: Section
    config_json: pydantic.Json = {}
    build_config_on_init: bool = False
    # cli_style: QuestionaryStyle = console.custom_style_dope
    model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.conf.sentry_enabled and self.conf.sentry_dsn:
            sentry_sdk.init(
                dsn=self.conf.sentry_dsn,
                traces_sample_rate=1.0,
                release=f"{__app_name__} v{__version__}",
            )
            logger.info("initialized sentry-sdk")

        if self.build_config_on_init:
            self.config_json = self.default_config_json
        else:
            service_config = self.load_config_from_tinydb()
            self.config_json = service_config.get("service_config", self.default_config_json)

        self.save_config_to_filesystem()
        self.save_config_to_tinydb()

    @property
    def handler_name(self):
        return self.__class__.__name__

    def __repr__(self):
        return self.handler_name

    def __str__(self):
        return self.handler_name

    @pydantic.computed_field
    def default_config_json(self) -> dict:
        section = self.config_section_class(self)
        config_json = json.loads(
            section.as_configuration().format(
                formatter="json",
                do_print=True,
            )
        )
        config_json["uwsgi"]["show-config"] = True
        return config_json

    def save_config_to_filesystem(self) -> None:
        self.service_config.parent.mkdir(
            parents=True, exist_ok=True
        )
        self.service_config.write_text(
                json.dumps(self.config_json)
        )

    def load_config_from_tinydb(self):
        return self.db.\
            table(self.tiny_db_table).\
            get(Query().service_id == self.service_id)

    def save_config_to_tinydb(self, extra_data: dict = {}) -> None:
        common_data = {
                "service_type": self.handler_name,
                "name": self.name,
                "service_id": self.service_id,
                "service_config": self.config_json,
        }
        common_data.update(extra_data)
        self.db.table(
                self.tiny_db_table
        ).upsert(
            common_data,
            Query().service_id == self.service_id
        )

    def up(self):
        pass

    @abstractmethod
    def start(self):
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        raise NotImplementedError

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
            console.warning(f"unknown master fifo command '{command}'")
            return

        if not all(
            [
                self.fifo_file,
                self.fifo_file.exists(),
            ]
        ):
            console.warning(f"invalid fifo file @ {self.fifo_file}")
            return

        with open(str(self.fifo_file), "w") as master_fifo:
            master_fifo.write(command)
            console.info(f"[pikesquares-services] : sent command [{command}] to master fifo")

    def ping(self) -> None:
        if not self.get_service_status() == "running":
            raise ServiceUnavailableError()

    def get_service_status(self) -> str:
        """
        read stats socket
        """
        if self.stats_address.exists() and self.stats_address.is_socket():
            return "running" if self.read_stats(str(self.stats_address)) else "stopped"

    def startup_log(self, show_config_start_marker: str, show_config_end_marker: str) -> Tuple[List, List]:
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
    #    if self.conf.CADDY_DIR and Path(self.conf.CADDY_DIR).exists():
    #        return Path(self.conf.CADDY_DIR)

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.config_dir) / f"{self.service_id}.json"

    @pydantic.computed_field
    def stats_address(self) -> Path:
        return Path(self.conf.run_dir) / f"{self.service_id}-stats.sock"

    @pydantic.computed_field
    def socket_address(self) -> Path:
        return Path(self.conf.run_dir) / f"{self.service_id}.sock"

    @pydantic.computed_field
    def notify_socket(self) -> Path:
        return Path(self.conf.run_dir) / f"{self.service_id}-notify.sock"

    @pydantic.computed_field
    def touch_reload_file(self) -> Path:
        return Path(self.conf.config_dir) / f"{self.service_id}.json"

    @pydantic.computed_field
    def pid_file(self) -> Path:
        return Path(self.conf.run_dir) / f"{self.service_id}.pid"

    @pydantic.computed_field
    def log_file(self) -> Path:
        return Path(self.conf.log_dir) / f"{self.service_id}.log"

    @pydantic.computed_field
    def fifo_file(self) -> Path:
        return Path(self.conf.run_dir) / f"{self.service_id}-master-fifo"

    # @pydantic.computed_field
    # def device_db_path(self) -> Path:
    #    return Path(self.conf.data_dir) / "device-db.json"

    @pydantic.computed_field
    def certificate(self) -> Path:
        return Path(self.conf.pki_dir) / "issued" / f"{self.cert_name}.crt"

    @pydantic.computed_field
    def certificate_key(self) -> Path:
        return Path(self.conf.pki_dir) / "private" / f"{self.cert_name}.key"

    @pydantic.computed_field
    def certificate_ca(self) -> Path:
        return Path(self.conf.pki_dir) / "ca.crt"

    @pydantic.computed_field
    def spooler_dir(self) -> Path:
        spdir = Path(self.conf.data_dir) / "spooler"
        if not spdir.exists():
            spdir.mkdir(parents=True, exist_ok=True)
        return spdir

    @classmethod
    def read_stats(cls, stats_address: Path):
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
