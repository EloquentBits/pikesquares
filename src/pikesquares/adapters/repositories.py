import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Type

import structlog
from sqlmodel import select, and_
from sqlmodel.sql.expression import SelectOfScalar
from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares.domain.base import ServiceBase
from pikesquares.domain.device import Device
from pikesquares.domain.project import Project
from pikesquares.domain.router import (
    BaseRouter,
    # HttpRouter,
    # HttpsRouter,
)

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


logger = structlog.get_logger()


T = TypeVar("T", bound=ServiceBase)


class GenericRepository(Generic[T], ABC):
    """Generic base repository.
    """

    @abstractmethod
    async def get_by_id(self, id: str) -> T | None:
        """Get a single record by id.

        Args:
            id (int): Record id.

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
    """Generic SQL Repository.
    """

    def __init__(self, session: AsyncSession, model_cls: Type[T]) -> None:
        """Creates a new repository instance.

        Args:
            session (AsyncSession): SQLModel session.
            model_cls (Type[T]): SQLModel class type.
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
            logger.debug(f"REPO {results=}")
            obj = results.first()
            logger.debug(f"REPO {obj=}")
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
        return await self._session.exec(stmt).all()

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
        record = self.get_by_id(id)
        if record is not None:
            await self._session.delete(record)
            await self._session.flush()


class DeviceReposityBase(GenericRepository[Device], ABC):
    """Device repository.
    """
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
            logger.debug(results)
            obj = results.first()
            logger.debug(obj)
            return obj


class ProjectReposityBase(GenericRepository[Project], ABC):
    """Project repository.
    """
    @abstractmethod
    async def get_by_name(self, name: str) -> Project | None:
        raise NotImplementedError()


class ProjectRepository(GenericSqlRepository[Project], ProjectReposityBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Project)

    async def get_by_name(self, name: str) -> Project | None:
        stmt = select(Project).where(Project.name == name)
        results = await self._session.exec(stmt)
        if results:
            logger.debug(results)
            obj = results.first()
            logger.debug(obj)
            return obj


class RouterReposityBase(GenericRepository[BaseRouter], ABC):
    """Router repository.
    """
    @abstractmethod
    async def get_by_name(self, name: str) -> BaseRouter | None:
        raise NotImplementedError()


class RouterRepository(GenericSqlRepository[BaseRouter], RouterReposityBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, BaseRouter)

    async def get_by_name(self, name: str) -> BaseRouter | None:
        stmt = select(BaseRouter).where(BaseRouter.name == name)
        results = await self._session.exec(stmt)
        if results:
            logger.debug(results)
            obj = results.first()
            logger.debug(obj)
            return obj
