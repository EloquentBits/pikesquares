from abc import ABC, abstractmethod
from typing import Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares.adapters.repositories import (
    DeviceReposityBase,
    DeviceRepository,
)


class UnitOfWorkBase(ABC):
    """Unit of work.
    """

    devices: DeviceReposityBase

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.rollback()

    @abstractmethod
    async def commit(self):
        """Commits the current transaction.
        """
        raise NotImplementedError()

    @abstractmethod
    async def rollback(self):
        """Rollbacks the current transaction.
        """
        raise NotImplementedError()


class UnitOfWork(UnitOfWorkBase):
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        """Creates a new uow instance.

        Args:
            session_factory (Callable[[], Session]): Session maker function.
        """
        self._session_factory = session_factory

    async def __aenter__(self):
        self._session = self._session_factory()
        self.devices = DeviceRepository(self._session)
        return await super().__aenter__()

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()
