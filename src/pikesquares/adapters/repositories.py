# import logging
from abc import ABC, abstractmethod
from typing import NewType, Generic, TypeVar, Sequence

import structlog
from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar

from pikesquares.domain.base import ServiceBase
from pikesquares.domain.device import Device, DeviceUWSGIOption
from pikesquares.domain.project import Project
from pikesquares.domain.router import (
    HttpRouter,
    TuntapRouter,
    TuntapDevice,
    # HttpRouter,
    # HttpsRouter,
)
from pikesquares.domain.wsgi_app import WsgiApp
from pikesquares.domain.monitors import ZMQMonitor
from pikesquares.domain.managed_services import AttachedDaemon

# logger = logging.getLogger("uvicorn.error")
# logger.setLevel(logging.DEBUG)

logger = structlog.get_logger()


T = TypeVar("T", bound=ServiceBase)

class GenericRepository(Generic[T], ABC):
    """Generic base repository."""

    @abstractmethod
    async def get_by_id(self, id: str) -> T | None:
        """Get a single record by id.

        Args:
            id (str): Record id.

        Returns:
            T | None: Record or none.
        """
        raise NotImplementedError()

    @abstractmethod
    async def get_by_service_id(self, service_id: str) -> T | None:
        """Get a single record by service_id.

        Args:
            service_id (str): Record service_id.

        Returns:
            T | None: Record or none.
        """
        raise NotImplementedError()

    @abstractmethod
    async def list(self, **filters) -> list[T]:
        """Gets a list of records

        Args:
            **filters: Filter conditions, several criteria are linked with a logical 'and'.

         Raises:
            ValueError: Invalid filter condition.

        Returns:
            list[T]: List of records.
        """
        raise NotImplementedError()

    @abstractmethod
    async def add(self, record: T) -> T:
        """Creates a new record.

        Args:
            record (T): The record to be created.

        Returns:
            T: The created record.
        """
        raise NotImplementedError()

    @abstractmethod
    async def update(self, record: T) -> T:
        """Updates an existing record.

        Args:
            record (T): The record to be updated incl. record id.

        Returns:
            T: The updated record.
        """
        raise NotImplementedError()

    @abstractmethod
    async def delete(self, id: str) -> None:
        """Deletes a record by id.

        Args:
            id (str): Record id.
        """
        raise NotImplementedError()


class GenericSqlRepository(GenericRepository[T], ABC):
    """Generic SQL Repository."""

    def __init__(self, session: AsyncSession, model_cls: type[T]) -> None:
        """Creates a new repository instance.

        Args:
            session (AsyncSession): SQLModel session.
            model_cls (type[T]): SQLModel class type.
        """
        self._session = session
        self._model_cls = model_cls

    def _construct_get_stmt(self, id: str) -> SelectOfScalar:
        """Creates a SELECT query for retrieving a single record.

        Args:
            id (str):  Record id.

        Returns:
            SelectOfScalar: SELECT statement.
        """
        stmt = select(self._model_cls).where(self._model_cls.id == id)
        return stmt

    async def get_by_id(self, id: str) -> T | None:
        stmt = self._construct_get_stmt(id)
        results = await self._session.exec(stmt)
        if results:
            obj = results.one_or_none()
            return obj

    async def get_by_service_id(self, service_id: str) -> T | None:
        stmt = select(self._model_cls).\
            where(self._model_cls.service_id == service_id)
        results = await self._session.exec(stmt)
        if results:
            obj = results.one_or_none()
            logger.debug(f"sql repo: retrieved by service_id {obj}")
            return obj

    def _construct_list_stmt(self, **filters) -> SelectOfScalar:
        """Creates a SELECT query for retrieving a multiple records.

        Raises:
            ValueError: Invalid column name.

        Returns:
            SelectOfScalar: SELECT statment.
        """
        stmt = select(self._model_cls)
        where_clauses = []
        for c, v in filters.items():
            if not hasattr(self._model_cls, c):
                raise ValueError(f"Invalid column name {c}")
            where_clauses.append(getattr(self._model_cls, c) == v)

        if len(where_clauses) == 1:
            stmt = stmt.where(where_clauses[0])
        elif len(where_clauses) > 1:
            stmt = stmt.where(and_(*where_clauses))
        return stmt

    async def list(self, **filters) -> list[T]:
        stmt = self._construct_list_stmt(**filters)
        results = await self._session.exec(stmt)
        return results.all()

    async def add(self, record: T) -> T:
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def update(self, record: T) -> T:
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return record

    async def delete(self, id: str) -> None:
        record: T = await self.get_by_id(id)
        if record is not None:
            await self._session.delete(record)
            await self._session.flush()


class DeviceReposityBase(GenericRepository[Device], ABC):
    """Device repository."""

    @abstractmethod
    async def get_by_machine_id(self, machine_id: str) -> Device | None:
        raise NotImplementedError()


class DeviceRepository(GenericSqlRepository[Device], DeviceReposityBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Device)

    async def get_by_machine_id(self, machine_id: str) -> Device | None:
        stmt = select(Device).where(Device.machine_id == machine_id)
        results = await self._session.exec(stmt)
        if results:
            obj = results.one_or_none()
            return obj


class DeviceUWSGIOptionsReposityBase(GenericRepository[DeviceUWSGIOption], ABC):
    """uwsgi options repository."""

    pass


class DeviceUWSGIOptionsRepository(GenericSqlRepository[DeviceUWSGIOption], DeviceUWSGIOptionsReposityBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DeviceUWSGIOption)

    async def get_by_device_id(self, device_id: str) -> list[DeviceUWSGIOption] | None:
        stmt = (
            select(DeviceUWSGIOption)
            .where(DeviceUWSGIOption.device_id == device_id)
            .order_by(DeviceUWSGIOption.sort_order_index)
        )
        results = await self._session.exec(stmt)
        if results:
            return results.all()


    """Project repository."""
class ProjectReposityBase(GenericRepository[Project], ABC):

    @abstractmethod
    async def get_by_name(self, name: str) -> Project | None:
        raise NotImplementedError()

    async def get_by_device_id(self, device_id: str) -> Sequence[Project] | None:
        raise NotImplementedError()

class ProjectRepository(GenericSqlRepository[Project], ProjectReposityBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Project)

    async def get_by_name(self, name: str) -> Project | None:
        stmt = select(Project).where(Project.name == name)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj

    async def get_by_device_id(self, device_id: str) -> Sequence[Project] | None:
        stmt = select(Project).where(Project.device_id == device_id)
        results = await self._session.exec(stmt)
        if results:
            return results.all()


class HttpRouterRepositoryBase(GenericRepository[HttpRouter], ABC):
    """Router repository."""

    @abstractmethod
    async def get_by_name(self, name: str) -> HttpRouter | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_project_id(self, project_id: str) -> Sequence[HttpRouter] | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_address(self, address: str) -> HttpRouter | None:
        raise NotImplementedError()


class HttpRouterRepository(GenericSqlRepository[HttpRouter], HttpRouterRepositoryBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, HttpRouter)

    async def get_by_name(self, name: str) -> HttpRouter | None:
        stmt = select(HttpRouter).where(HttpRouter.name == name)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj

    async def get_by_project_id(self, project_id: str) -> Sequence[HttpRouter] | None:
        stmt = select(HttpRouter).where(HttpRouter.project_id == project_id)
        results = await self._session.exec(stmt)
        if results:
            return results.all()

    async def get_by_address(self, address: str) -> HttpRouter | None:
        stmt = select(HttpRouter).where(HttpRouter.address == address)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj



class WsgiAppReposityBase(GenericRepository[WsgiApp], ABC):
    """WsgiApp repository."""

    @abstractmethod
    async def get_by_name(self, name: str) -> WsgiApp | None:
        raise NotImplementedError()


class WsgiAppRepository(GenericSqlRepository[WsgiApp], WsgiAppReposityBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WsgiApp)

    async def get_by_name(self, name: str) -> WsgiApp | None:
        stmt = select(WsgiApp).where(WsgiApp.name == name)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj

    async def get_by_project_id(self, project_id: str) -> Sequence[WsgiApp] | None:
        stmt = select(WsgiApp).where(WsgiApp.project_id == project_id)
        results = await self._session.exec(stmt)
        if results:
            return results.all()


class ZMQMonitorRepositoryBase(GenericRepository[ZMQMonitor], ABC):
    """ZMQMonitor repository."""

    @abstractmethod
    async def get_by_transport(self, transport: str) -> ZMQMonitor | None:
        raise NotImplementedError()


class ZMQMonitorRepository(GenericSqlRepository[ZMQMonitor], ZMQMonitorRepositoryBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ZMQMonitor)

    async def get_by_device_id(self, device_id: str) -> ZMQMonitor | None:
        stmt = select(ZMQMonitor).where(ZMQMonitor.device_id == device_id)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj

    async def get_by_project_id(self, project_id: str) -> ZMQMonitor | None:
        stmt = select(ZMQMonitor).where(ZMQMonitor.project_id == project_id)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj

    async def get_by_transport(self, transport: str) -> ZMQMonitor | None:
        stmt = select(ZMQMonitor).where(ZMQMonitor.transport == transport)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj

    # async def get_by_project_id(self, project_id: str) -> WsgiApp | None:
    #    stmt = select(WsgiApp).where(WsgiApp.project_id == project_id)
    #    results = await self._session.exec(stmt)
    #    if results:
    ##        return results.all()



class TuntapRouterRepositoryBase(GenericRepository[TuntapRouter], ABC):
    """TuntapRouter repository."""

    @abstractmethod
    async def get_by_name(self, name: str) -> TuntapRouter | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_project_id(self, project_id: str) -> Sequence[TuntapRouter] | None:
        raise NotImplementedError()


class TuntapRouterRepository(GenericSqlRepository[TuntapRouter], TuntapRouterRepositoryBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TuntapRouter)

    async def get_by_name(self, name: str) -> TuntapRouter | None:
        stmt = select(TuntapRouter).where(TuntapRouter.name == name)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj

    async def get_by_project_id(self, project_id: str) -> Sequence[TuntapRouter] | None:
        stmt = (
            select(TuntapRouter)
            .where(TuntapRouter.project_id == project_id)
        )
        results = await self._session.exec(stmt)
        if results:
            return results.all()

    async def get_by_ip(self, ip: str) -> TuntapRouter | None:
        stmt = select(TuntapRouter).where(TuntapRouter.ip == ip)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj


class TuntapDeviceRepositoryBase(GenericRepository[TuntapDevice], ABC):
    """TuntapDevice repository."""

    @abstractmethod
    async def get_by_name(self, name: str) -> TuntapDevice | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_tuntap_router_id(self, tuntap_router_id: str) -> Sequence[TuntapDevice] | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_ip(self, ip: str) -> TuntapDevice | None:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_linked_service_id(self, linked_service_id: str) -> TuntapDevice | None:
        raise NotImplementedError()

class TuntapDeviceRepository(GenericSqlRepository[TuntapDevice], TuntapDeviceRepositoryBase):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TuntapDevice)

    async def get_by_name(self, name: str) -> TuntapDevice | None:
        stmt = select(TuntapDevice).where(TuntapDevice.name == name)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj

    async def get_by_tuntap_router_id(self, tuntap_router_id: str) -> Sequence[TuntapDevice] | None:
        stmt = (
            select(TuntapDevice)
            .where(TuntapDevice.tuntap_router_id == tuntap_router_id)
        )
        results = await self._session.exec(stmt)
        if results:
            return results.all()

    async def get_by_ip(self, ip: str) -> TuntapDevice | None:
        stmt = select(TuntapDevice).where(TuntapDevice.ip == ip)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj

    async def get_by_linked_service_id(self, linked_service_id: str) -> TuntapDevice | None:
        stmt = select(TuntapDevice).where(TuntapDevice.linked_service_id == linked_service_id)
        results = await self._session.exec(stmt)
        if results:
            obj = results.first()
            return obj

#ZMQMonitorRepository = NewType("ZMQMonitorRepository", ZMQMonitorRepositoryBase)


class AttachedDaemonRepositoryBase(GenericRepository[AttachedDaemon], ABC):
    """AttachedDaemon repository."""

    @abstractmethod
    async def for_project_by_name(self, name: str, project_id: str) -> Sequence[AttachedDaemon] | None:
        raise NotImplementedError()


class AttachedDaemonRepository(GenericSqlRepository[AttachedDaemon], AttachedDaemonRepositoryBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AttachedDaemon)

    async def for_project_by_name(self, name: str, project_id: str) -> Sequence[AttachedDaemon] | None:
        stmt = select(AttachedDaemon).where(
            AttachedDaemon.name == name,
            AttachedDaemon.project_id == project_id,
        )
        results = await self._session.exec(stmt)
        return results.all()
