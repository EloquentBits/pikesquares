import logging
from abc import ABC, abstractmethod

from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares.adapters.repositories import (
    DeviceReposityBase,
    DeviceRepository,
)

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


class UnitOfWorkBase(ABC):
    """Unit of work.
    """

    devices: DeviceReposityBase

    async def __aenter__(self):
        return self

    # @abstractmethod
    # async def __aexit__(self, exc_type, exc_value, traceback):
    #    raise NotImplementedError()

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
    def __init__(self, session: AsyncSession) -> None:
        """Creates a new uow instance.

        Args:
            session_factory (Callable[[], AsyncSession]): Session maker function.
        """
        self._session = session

    async def __aenter__(self):
        self.devices = DeviceRepository(self._session)
        return await super().__aenter__()

    async def __aexit__(self, *args):
        # await super().__aexit__(*args)
        await self._session.close()

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()
