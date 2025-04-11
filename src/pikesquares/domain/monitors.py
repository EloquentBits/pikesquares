import enum
import uuid

# from pathlib import Path

# from typing import Any

import zmq
import zmq.asyncio
import pydantic
import structlog

from sqlmodel import (
    Field,
    SQLModel,
    Relationship,
    # Column,
    # Enum,
)
from sqlalchemy_utils import ChoiceType


from .device import Device
from .project import Project
from .base import TimeStampedBase  # , enum_values

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
    socket: str | None = Field(max_length=150, default=None)
    transport: str | None = Field(max_length=10, default=None)

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
    @pydantic.computed_field
    @property
    def address(self) -> str | None:
        if self.transport == "tcp":  # ZMQMonitor.ZMQTransport.TCP:
            if self.ip and self.port:
                return f"zmq://tcp://{self.ip}:{self.port}"

        elif self.transport == "ipc":  # ZMQMonitor.ZMQTransport.IPC:
            return f"zmq://ipc://{self.socket}"

    async def create_instance(self, name: str, uwsgi_config: str) -> None:
        ctx = zmq.asyncio.Context()
        sock = ctx.socket(zmq.PUSH)
        if self.address:
            logger.debug(f"connecting to ZMQ Monitor @ {self.address}")
            sock.connect(self.address)
            await sock.send_multipart([b"touch", name.encode(), uwsgi_config.encode])

    async def restart_instance(self, name: str, uwsgi_config: str) -> None:
        ctx = zmq.asyncio.Context()
        sock = ctx.socket(zmq.PUSH)
        if self.address:
            sock.connect(self.address)
            # uwsgi_config = self.get_uwsgi_config()
            # uwsgi_config.format(do_print=True)
            await sock.send_multipart([b"touch", name.encode(), uwsgi_config.encode()])

    async def destroy_instance(self, name: str) -> None:
        ctx = zmq.asyncio.Context()
        sock = ctx.socket(zmq.PUSH)
        if self.address:
            sock.connect(self.address)
            await sock.send_multipart([b"destroy", name.encode()])


class DirMonitor(AppMonitorBase, table=True):
    """dir/glob imperial monitor"""

    __tablename__ = "dir_monitors"

    directory: str | None = Field(max_length=255, default=None)
    pattern: str | None = Field(max_length=255, default=None)
