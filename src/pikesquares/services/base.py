from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, List

import pydantic
from pydantic.config import ConfigDict
from tinydb import TinyDB
from uwsgiconf import uwsgi
import sentry_sdk

from pikesquares import __version__, __app_name__
from pikesquares import conf
from pikesquares import read_stats
from pikesquares.cli.console import console


__all__ = (
    "BaseService",
)


class BaseService(pydantic.BaseModel, ABC):

    conf: conf.ClientConfig
    db: TinyDB
    service_id: str
    # cache:str = "pikesquares-settings"
    parent_service_id: str | None = None
    cert_name: str = "_wildcard_pikesquares_dev"
    name: str = ""
    is_internal: bool = True
    is_enabled: bool = False
    is_app: bool = False
    config_json: pydantic.Json = {}
    # cli_style: QuestionaryStyle = console.custom_style_dope
    model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)

    #def __init__(self):
    #    if self.conf.SENTRY_ENABLED and self.conf.SENTRY_DSN:
    #        sentry_sdk.init(
    #            dsn=self.conf.SENTRY_DSN,
    #            traces_sample_rate=1.0,
    #            release=f"{__app_name__} v{__version__}",
    #        )
            # console.success("initialized sentry-sdk")

    @property
    def handler_name(self):
        return self.__class__.__name__

    def __repr__(self):
        return self.handler_name

    def __str__(self):
        return self.handler_name

    @abstractmethod
    def connect(self):
        raise NotImplementedError

    @abstractmethod
    def prepare_service_config(self):
        raise NotImplementedError

    @abstractmethod
    def start(self):
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        raise NotImplementedError

    def write_master_fifo(self, command: str) -> None:
        """
        Write command to master fifo named pipe

        ‘0’ to ‘9’ - set the fifo slot (see below)
        ‘+’ - increase the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
        ‘-’ - decrease the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
        ‘B’ - ask Emperor for reinforcement (broodlord mode, requires uWSGI >= 2.0.7)
        ‘C’ - set cheap mode
        ‘c’ - trigger chain reload
        ‘E’ - trigger an Emperor rescan
        ‘f’ - re-fork the master (dangerous, but very powerful)
        ‘l’ - reopen log file (need –log-master and –logto/–logto2)
        ‘L’ - trigger log rotation (need –log-master and –logto/–logto2)
        ‘p’ - pause/resume the instance
        ‘P’ - update pidfiles (can be useful after master re-fork)
        ‘Q’ - brutally shutdown the instance
        ‘q’ - gracefully shutdown the instance
        ‘R’ - send brutal reload
        ‘r’ - send graceful reload
        ‘S’ - block/unblock subscriptions
        ‘s’ - print stats in the logs
        ‘W’ - brutally reload workers
        ‘w’ - gracefully reload workers
        """

        if not command in ["r", "q", "s"]:
            console.warning("unknown master fifo command '{command}'")
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

    def get_service_status(self):
        """
        read stats socket
        """
        if self.stats_address.exists() and self.stats_address.is_socket():
            return 'running' if read_stats(str(self.stats_address)) else 'stopped'

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

    @pydantic.computed_field
    def easyrsa(self) -> str:
        return self.conf.EASYRSA_DIR / "EasyRSA-3.2.1" / "easyrsa"

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
        return Path(self.conf.CONFIG_DIR) / f"{self.service_id}.json"

    @pydantic.computed_field
    def stats_address(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}-stats.sock"

    @pydantic.computed_field
    def socket_address(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}.sock"

    @pydantic.computed_field
    def notify_socket(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}-notify.sock"

    @pydantic.computed_field
    def touch_reload_file(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / f"{self.service_id}.json"

    @pydantic.computed_field
    def pid_file(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}.pid"

    @pydantic.computed_field
    def log_file(self) -> Path:
        return Path(self.conf.LOG_DIR) / f"{self.service_id}.log"

    @pydantic.computed_field
    def fifo_file(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}-master-fifo"

    # @pydantic.computed_field
    # def device_db_path(self) -> Path:
    #    return Path(self.conf.DATA_DIR) / "device-db.json"

    @pydantic.computed_field
    def certificate(self) -> Path:
        return Path(self.conf.PKI_DIR) / "issued" / f"{self.cert_name}.crt"

    @pydantic.computed_field
    def certificate_key(self) -> Path:
        return Path(self.conf.PKI_DIR) / "private" / f"{self.cert_name}.key"

    @pydantic.computed_field
    def certificate_ca(self) -> Path:
        return Path(self.conf.PKI_DIR) / "ca.crt"
