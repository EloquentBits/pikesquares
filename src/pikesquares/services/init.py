from collections.abc import Iterator

import apluggy as pluggy
import structlog
import typer
from sqlmodel import Session, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares import services
from pikesquares.adapters.database import AsyncDatabaseSessionManager, DatabaseSessionManager
from pikesquares.cli.console import console
from pikesquares.conf import AppConfig
from pikesquares.domain.base import ServiceBase
from pikesquares.domain.process_compose import (
    register_process_compose,
)
from pikesquares.hooks.specs import plugin_manager_factory
from pikesquares.service_layer.handlers.device import provision_device
from pikesquares.service_layer.handlers.monitors import create_zmq_monitor
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger(__name__)


def init_db(context):

    conf = services.get(context, AppConfig)

    sessionmanager = DatabaseSessionManager(conf.SQLALCHEMY_DATABASE_URI, {"echo": False})

    def get_session() -> Iterator[Session]:
        with sessionmanager.session() as session:
            yield session

    services.register_factory(context, Session, get_session)  # ping=lambda session: session.execute(text("SELECT 1")),
    session = services.get(context, Session)

    with sessionmanager.connect() as conn:
        SQLModel.metadata.create_all(conn)

        # async with sessionmanager._engine.begin() as conn:
        #    await conn.run_sync(
        #       lambda conn: SQLModel.metadata.create_all(conn)
        #    )

    # generate the version table, "stamping" it with the most recent rev:
    # alembic_cfg = Config("/home/pk/dev/eqb/pikesquares/alembic.ini")
    # command.stamp(alembic_cfg, "head")

    def uow_factory():
        with UnitOfWork(session=session) as uow:
            yield uow

    services.register_factory(context, UnitOfWork, uow_factory)


async def init_db_async(context):

    conf = services.get(context, AppConfig)

    sessionmanager = AsyncDatabaseSessionManager(conf.SQLALCHEMY_DATABASE_URI, {"echo": False})

    async def get_session() -> AsyncSession:
        async with sessionmanager.session() as session:
            return session

    services.register_factory(
        context, AsyncSession, get_session
    )  # ping=lambda session: session.execute(text("SELECT 1")),
    session = await services.aget(context, AsyncSession)

    async with sessionmanager.connect() as conn:
        await conn.run_sync(lambda conn: SQLModel.metadata.create_all(conn))
        # async with sessionmanager._engine.begin() as conn:
        #    await conn.run_sync(
        #       lambda conn: SQLModel.metadata.create_all(conn)
        #    )
    # generate the version table, "stamping" it with the most recent rev:
    # alembic_cfg = Config("/home/pk/dev/eqb/pikesquares/alembic.ini")
    # command.stamp(alembic_cfg, "head")

    async def uow_factory():
        async with UnitOfWork(session=session) as uow:
            yield uow

    services.register_factory(context, UnitOfWork, uow_factory)

    # plugin_manager = await services.aget(context, pluggy.PluginManager)
    # plugin_manager.register(
    #    PythonRuntimePlugin(),
    # )

    """
    def attached_daemon_plugin_manager_factory():
        pm = PluginManager("attached-daemon")
        pm.add_hookspecs(AttachedDaemonHookSpec)
        return pm
    services.register_factory(context, AttachedDaemonPluginManager , attached_daemon_plugin_manager_factory)
    #attached_daemon_plugin_manager = await services.aget(context, AttachedDaemonPluginManager)

    def app_runtime_plugin_manager_factory():
        pm = PluginManager("app-runtime")
        # magic line to set a writer function
        pm.trace.root.setwriter(print)
        undo = pm.enable_tracing()
        pm.add_hookspecs(AppRuntimeHookSpec)
        return pm
    services.register_factory(
        context,
        AppRuntimePluginManager,
        app_runtime_plugin_manager_factory
    )
    def wsgi_app_plugin_manager_factory():
        pm = PluginManager("wsgi-app")
        # magic line to set a writer function
        pm.trace.root.setwriter(print)
        undo = pm.enable_tracing()
        pm.add_hookspecs(WsgiAppHookSpec)
        return pm
    services.register_factory(
        context,
        WsgiAppPluginManager,
        wsgi_app_plugin_manager_factory
    )
    #app_runtime_plugin_manager = await services.aget(context, AppRuntimePluginManager)
    """


def init_device(context):

    uow = services.get(context, UnitOfWork)
    conf = services.get(context, AppConfig)

    try:
        machine_id = ServiceBase.read_machine_id()
        device = uow.devices.get_by_machine_id(machine_id)
        if not device:
            device = provision_device(
                uow,
                create_kwargs={
                    "data_dir": str(conf.data_dir),
                    "config_dir": str(conf.config_dir),
                    "log_dir": str(conf.log_dir),
                    "run_dir": str(conf.run_dir),
                },
            )
            zmq_monitor = create_zmq_monitor(uow, device=device)
            if not zmq_monitor.socket_address:
                console.error("device zmq monitor socket address was not provisioned")
                raise typer.Exit(1)
            logger.info(f"created device zmq_monitor @ {zmq_monitor.socket_address}")

        uwsgi_options = device.uwsgi_options
        if not uwsgi_options:
            for uwsgi_option in device.get_uwsgi_options():
                uow.uwsgi_options.add(uwsgi_option)

        uow.commit()
        return device

    except Exception as exc:
        logger.exception(exc)
        console.error("device was not created")
        uow.rollback()
        raise typer.Exit(1) from None

    # pc = services.get(context, ProcessCompose)


def init_process_compose(context, device):
    uow = services.get(context, UnitOfWork)
    register_process_compose(context, device.machine_id, uow)


def init_pluggy(context):
    services.register_factory(
        context,
        pluggy.PluginManager,
        plugin_manager_factory,
    )
