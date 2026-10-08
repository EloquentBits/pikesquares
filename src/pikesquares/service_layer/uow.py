from abc import ABC, abstractmethod

import structlog
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares.adapters.repositories import (
    AttachedDaemonRepository,
    AttachedDaemonRepositoryBase,
    DeviceRepository,
    DeviceReposityBase,
    DeviceUWSGIOptionsRepository,
    DeviceUWSGIOptionsReposityBase,
    HttpRouterRepository,
    HttpRouterRepositoryBase,
    ProjectRepository,
    ProjectReposityBase,
    PythonAppCodebaseRepository,
    PythonAppCodebaseRepositoryBase,
    PythonAppRuntimeRepository,
    PythonAppRuntimeRepositoryBase,
    TuntapDeviceRepository,
    TuntapDeviceRepositoryBase,
    TuntapRouterRepository,
    TuntapRouterRepositoryBase,
    WsgiAppRepository,
    WsgiAppReposityBase,
    ZMQMonitorRepository,
    ZMQMonitorRepositoryBase,
)

# logger = logging.getLogger("uvicorn.error")
# logger.setLevel(logging.DEBUG)


logger = structlog.get_logger()


class AsyncUnitOfWorkBase(ABC):
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
    python_app_codebases: PythonAppCodebaseRepositoryBase

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


class AsyncUnitOfWork(AsyncUnitOfWorkBase):
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
        self.python_app_codebases = PythonAppCodebaseRepository(self._session)
        return await super().__aenter__()

    async def __aexit__(self, *args):
        await self._session.close()

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()


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
    python_app_codebases: PythonAppCodebaseRepositoryBase

    def __enter__(self):
        return self

    # @abstractmethod
    # async def __aexit__(self, exc_type, exc_value, traceback):
    #    raise NotImplementedError()

    @abstractmethod
    def commit(self):
        """Commits the current transaction."""
        raise NotImplementedError()

    @abstractmethod
    def rollback(self):
        """Rollbacks the current transaction."""
        raise NotImplementedError()


class UnitOfWork(UnitOfWorkBase):
    def __init__(self, session: Session) -> None:
        """Creates a new uow instance.

        Args:
            session_factory (Callable[[], Session]): Session maker function.
        """
        self._session = session

    def __enter__(self):
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
        self.python_app_codebases = PythonAppCodebaseRepository(self._session)
        return super().__enter__()

    def __exit__(self, *args):
        self._session.close()

    def commit(self):
        self._session.commit()

    def rollback(self):
        self._session.rollback()
