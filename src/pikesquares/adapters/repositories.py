import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Type

from sqlmodel import select, and_
from sqlmodel.sql.expression import SelectOfScalar
from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares.domain.base import ServiceBase
from pikesquares.domain.device import Device

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


T = TypeVar("T", bound=ServiceBase)


class GenericRepository(Generic[T], ABC):
    """Generic base repository.
    """

    @abstractmethod
    async def get_by_id(self, id: int) -> T | None:
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
    async def delete(self, id: int) -> None:
        """Deletes a record by id.

        Args:
            id (int): Record id.
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

    def _construct_get_stmt(self, id: int) -> SelectOfScalar:
        """Creates a SELECT query for retrieving a single record.

        Args:
            id (int):  Record id.

        Returns:
            SelectOfScalar: SELECT statement.
        """
        stmt = select(self._model_cls).where(self._model_cls.id == id)
        return stmt

    async def get_by_id(self, id: int) -> T | None:
        stmt = self._construct_get_stmt(id)
        return await self._session.exec(stmt).first()

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

    async def delete(self, id: int) -> None:
        record = self.get_by_id(id)
        if record is not None:
            await self._session.delete(record)
            await self._session.flush()


class DeviceReposityBase(GenericRepository[Device], ABC):
    """DeviceHero repository.
    """
    @abstractmethod
    async def get_by_id(self, id: int) -> Device | None:
        raise NotImplementedError()


class DeviceRepository(GenericSqlRepository[Device], DeviceReposityBase):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Device)

    async def get_by_id(self, id: int) -> Device | None:
        #stmt = select(Device).where(Device.service_id == service_id)

        return await self._session.get(Device, id)

        # await self._session.exec(select(Hero)).all()

        # return await self._session.exec(stmt)
