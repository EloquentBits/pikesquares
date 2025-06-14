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
    HttpRouterRepository,
    HttpRouterRepositoryBase,
    WsgiAppRepository,
    WsgiAppReposityBase,
    ZMQMonitorRepository,
    ZMQMonitorRepositoryBase,
    TuntapRouterRepositoryBase,
    TuntapRouterRepository,
    TuntapDeviceRepositoryBase,
    TuntapDeviceRepository,
    AttachedDaemonRepositoryBase,
    AttachedDaemonRepository,
    PythonAppRuntimeRepositoryBase,
    PythonAppRuntimeRepository,
    AppCodebaseRepositoryBase,
    AppCodebaseRepository,
)

# logger = logging.getLogger("uvicorn.error")
# logger.setLevel(logging.DEBUG)


logger = structlog.get_logger()


class UnitOfWorkBase(ABC):
    """Unit of work."""

    devices: DeviceReposityBase
    uwsgi_options: DeviceUWSGIOptionsReposityBase
    projects: ProjectReposityBase
    http_routers: HttpRouterRepositoryBase
    wsgi_apps: WsgiAppReposityBase
    zmq_monitors: ZMQMonitorRepositoryBase
    tuntap_routers: TuntapRouterRepositoryBase
    tuntap_devices: TuntapDeviceRepositoryBase
    attached_daemons: AttachedDaemonRepositoryBase
    python_app_runtimes: PythonAppRuntimeRepositoryBase
    app_codebases: AppCodebaseRepositoryBase

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
        self.http_routers = HttpRouterRepository(self._session)
        self.wsgi_apps = WsgiAppRepository(self._session)
        self.zmq_monitors = ZMQMonitorRepository(self._session)
        self.tuntap_routers = TuntapRouterRepository(self._session)
        self.tuntap_devices = TuntapDeviceRepository(self._session)
        self.attached_daemons = AttachedDaemonRepository(self._session)
        self.python_app_runtimes = PythonAppRuntimeRepository(self._session)
        self.app_codebases = AppCodebaseRepository(self._session)
        return await super().__aenter__()

    async def __aexit__(self, *args):
        await self._session.close()

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()
