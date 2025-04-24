from abc import ABC, abstractmethod

import structlog
from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares.adapters.repositories import (
    DeviceRepository,
    DeviceReposityBase,
    DeviceUWSGIOptionsRepository,
    DeviceUWSGIOptionsReposityBase,
    ProjectRepository,
    ProjectReposityBase,
    RouterRepository,
    RouterRepositoryBase,
    WsgiAppRepository,
    WsgiAppReposityBase,
    ZMQMonitorRepository,
    ZMQMonitorRepositoryBase,
)

# logger = logging.getLogger("uvicorn.error")
# logger.setLevel(logging.DEBUG)


logger = structlog.get_logger()


class UnitOfWorkBase(ABC):
    """Unit of work."""

    devices: DeviceReposityBase
    uwsgi_options: DeviceUWSGIOptionsReposityBase
    projects: ProjectReposityBase
    routers: RouterRepositoryBase
    wsgi_apps: WsgiAppReposityBase
    zmq_monitors: ZMQMonitorRepositoryBase

    async def __aenter__(self):
        return self

    # @abstractmethod
    # async def __aexit__(self, exc_type, exc_value, traceback):
    #    raise NotImplementedError()

    @abstractmethod
    async def commit(self):
        """Commits the current transaction."""
        raise NotImplementedError()

    @abstractmethod
    async def rollback(self):
        """Rollbacks the current transaction."""
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
        self.uwsgi_options = DeviceUWSGIOptionsRepository(self._session)
        self.projects = ProjectRepository(self._session)
        self.routers = RouterRepository(self._session)
        self.wsgi_apps = WsgiAppRepository(self._session)
        self.zmq_monitors = ZMQMonitorRepository(self._session)
        return await super().__aenter__()

    async def __aexit__(self, *args):
        logger.debug("UOW close session")
        await self._session.close()

    async def commit(self):
        logger.debug("UOW commit session")
        await self._session.commit()

    async def rollback(self):
        logger.debug("UOW rollback session")
        await self._session.rollback()
