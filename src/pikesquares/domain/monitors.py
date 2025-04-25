import enum
import uuid

import structlog

# from pathlib import Path
# from typing import Any
import zmq
import zmq.asyncio

# from sqlalchemy_utils import ChoiceType
from sqlmodel import (
    Field,
    Relationship,
    # Column,
    # Enum,
    SQLModel,
)

from .base import TimeStampedBase  # , enum_values
from .device import Device
from .project import Project

logger = structlog.getLogger()


# MONITOR_TYPES = [('zeromq', 'ZeroMQ Monitor'), ('dir', 'Dir Monitor')]
# class MonitorTypes(str, enum.Enum):
#    zeromq = "ZeroMQ Monitor"
#    dir = "Dir Monitor"


class AppMonitorBase(TimeStampedBase, SQLModel):

    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4()),
        max_length=36,
    )
    # monitor_type: MONITOR_TYPES = Field(sa_column=Column(ChoiceType(MONITOR_TYPES)))
    # monitor_type: MonitorTypes = Column(Enum(MonitorTypes))
    # monitor_type: MonitorTypes = Field(sa_column=Column(Enum(MonitorTypes)))

    # impl=Integer()), nullable=False

    # monitor_type: MonitorType = Field(
    #    sa_type=Column(
    #        name="monitor_type",
    #        nullable=False,
    #        type_=Enum(MonitorType, values_callable=enum_values),
    #    )
    # )


# ZMQ_TRANSPORTS = [
#    ("ipc", "IPC"),
#    ("tcp", "TCP"),
# ]


class ZMQMonitor(AppMonitorBase, table=True):
    """Zeromq imperial monitor"""

    __tablename__ = "zmq_monitors"

    ip: str | None = Field(max_length=25, default=None)
    port: int | None = Field(default=None)
    transport: str | None = Field(max_length=10, default=None)
    socket: str | None = Field(max_length=150, default=None)

    device_id: int | None = Field(foreign_key="devices.id", unique=True)
    device: Device | None = Relationship(back_populates="zmq_monitor")

    project_id: int | None = Field(foreign_key="projects.id", unique=True)
    project: Project | None = Relationship(back_populates="zmq_monitor")

    # transport: ZMQ_TRANSPORTS = Field(sa_type=Column(ChoiceType(ZMQ_TRANSPORTS)))

    # transport: ZMQTransport = Field(
    #    sa_type=Column(
    #        name="transport",
    #        nullable=False,
    #        type_=Enum(ZMQTransport, values_callable=enum_values),
    #    )
    # )
    #
    @property
    def zmq_address(self) -> str | None:
        if self.transport == "tcp":  # ZMQMonitor.ZMQTransport.TCP:
            if self.ip and self.port:
                return f"tcp://{self.ip}:{self.port}"

        elif self.transport == "ipc":  # ZMQMonitor.ZMQTransport.IPC:
            return f"ipc://{self.socket}"

    @property
    def uwsgi_zmq_address(self) -> str | None:
        return f"zmq://{self.zmq_address}"

    async def create_or_restart_instance(self, name: str, model: Device | Project, zmq_monitor=None) -> None:
        ctx = zmq.asyncio.Context()
        sock = ctx.socket(zmq.PUSH)
        if self.zmq_address:
            logger.debug(f"Launching {model.__class__.__name__} {model.service_id} in ZMQ Monitor @ {self.zmq_address}")
            uwsgi_config = model.get_uwsgi_config(zmq_monitor=zmq_monitor)
            logger.debug(uwsgi_config)
            sock.connect(self.zmq_address)
            await sock.send_multipart([b"touch", name.encode(), uwsgi_config.format(do_print=True).encode()])
        else:
            logger.info(f"{model.__class__.__name__} no zmq socket found @ {self.zmq_address}")

    async def destroy_instance(self, name: str, model: Device | Project) -> None:
        ctx = zmq.asyncio.Context()
        sock = ctx.socket(zmq.PUSH)
        if self.zmq_address:
            sock.connect(self.zmq_address)
            logger.debug(f"Stopping {model.__class__.__name__} {model.service_id} in ZMQ Monitor @ {self.zmq_address}")
            await sock.send_multipart([b"destroy", name.encode()])


class DirMonitor(AppMonitorBase, table=True):
    """dir/glob imperial monitor"""

    __tablename__ = "dir_monitors"

    directory: str | None = Field(max_length=255, default=None)
    pattern: str | None = Field(max_length=255, default=None)
