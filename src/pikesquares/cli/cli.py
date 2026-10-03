import asyncio
import atexit
import grp
import logging
import os
from pathlib import Path
from typing import Annotated

import apluggy as pluggy
import sentry_sdk

# import structlog
import structlog_sentry_logger
import typer
from dotenv import load_dotenv
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares import __app_name__, __version__, services
from pikesquares.adapters.database import DatabaseSessionManager
from pikesquares.cli.decorator import run_async
from pikesquares.conf import (
    AppConfig,
    AppConfigError,
    register_app_conf,
)
from pikesquares.domain.base import ServiceBase
from pikesquares.domain.process_compose import (
    register_process_compose,
)
from pikesquares.hooks.specs import plugin_manager_factory
from pikesquares.service_layer.handlers.device import provision_device
from pikesquares.service_layer.handlers.monitors import create_zmq_monitor
from pikesquares.service_layer.uow import UnitOfWork

from .console import console

LOG_FILE = "app.log"

"""
def write_to_file(logger, method_name, event_dict):
    with open(LOG_FILE, "a") as log_file:
        log_file.write(json.dumps(event_dict) + "\n")
    return event_dict  # Required by structlog's processor chain

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),  # Add timestamp
        structlog.processors.JSONRenderer(),  # Format as JSON
        write_to_file,  # Write to file
    ],
    context_class=dict,  # Use a standard dictionary for context
    logger_factory=structlog.PrintLoggerFactory(),  # PrintLoggerFactory is required but won't print due to write_to_file
    wrapper_class=structlog.BoundLogger,
    cache_logger_on_first_use=True,
)
"""

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    # stream=sys.stdout,
    format="%(message)s",
)
for import_lib in ["svcs", "asyncio", "aiosqlite", "plumbum"]:
    warn_logger = logging.getLogger(import_lib)
    warn_logger.setLevel(logging.WARNING)

"""
structlog.configure(
    processors=[
        # If log level is too low, abort pipeline and throw away log entry.
        structlog.stdlib.filter_by_level,
        # Add the name of the logger to event dict.
        structlog.stdlib.add_logger_name,
        # Add log level to event dict.
        structlog.stdlib.add_log_level,
        # Perform %-style formatting.
        structlog.stdlib.PositionalArgumentsFormatter(),
        # Add a timestamp in ISO 8601 format.
        structlog.processors.TimeStamper(fmt="iso"),
        # If the "stack_info" key in the event dict is true, remove it and
        # render the current stack trace in the "stack" key.
        structlog.processors.StackInfoRenderer(),
        # If the "exc_info" key in the event dict is either true or a
        # sys.exc_info() tuple, remove "exc_info" and render the exception
        # with traceback into the "exception" key.
        structlog.processors.format_exc_info,
        # If some value is in bytes, decode it to a Unicode str.
        structlog.processors.UnicodeDecoder(),
        # Add callsite parameters.
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()
"""

logger = structlog_sentry_logger.get_logger()

load_dotenv()


app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_short=False,
    pretty_exceptions_show_locals=False,
)


from .commands import apps, control, devices, managed_services, projects, routers

app.add_typer(control.app)
app.add_typer(apps.app, name="apps")
app.add_typer(routers.app, name="routers")
app.add_typer(projects.app, name="projects")
app.add_typer(devices.app, name="devices")
app.add_typer(managed_services.app, name="services")


def _version_callback(value: bool) -> None:
    if value:
        console.info(f"{__app_name__} v{__version__}")
        raise typer.Exit()


@app.callback()
@run_async
async def main(
    ctx: typer.Context,
    version: str | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show PikeSquares version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    data_dir: Annotated[
        Path | None,
        typer.Option(
            "--data-dir",
            "-d",
            exists=True,
            # file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
            help="Data directory",
        ),
    ] = None,
    config_dir: Annotated[
        Path | None,
        typer.Option(
            "--config-dir",
            "-c",
            exists=True,
            # file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
            help="Configs directory",
        ),
    ] = None,
    log_dir: Annotated[
        Path | None,
        typer.Option(
            "--log-dir",
            "-l",
            exists=True,
            # file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
            help="Logs directory",
        ),
    ] = None,
    run_dir: Annotated[
        Path | None,
        typer.Option(
            "--run-dir",
            "-r",
            exists=True,
            # file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
            help="Run directory",
        ),
    ] = None,
) -> None:
    """
    Welcome to Pike Squares. Building blocks for your apps.
    """

    # logger.info(f"About to execute command: {ctx.invoked_subcommand}")
    is_root: bool = os.getuid() == 0

    # FIXME make sure to make an exception for --help
    if ctx.invoked_subcommand in set(
        {
            "up",
        }
    ):
        if not is_root:
            console.info("Please start server as root user. `sudo pikesquares up`")
            raise typer.Exit()

        # continue running as `pikesquares` group
        try:
            os.setgid(grp.getgrnam("pikesquares")[2])
        except IndexError:
            # TODO
            # create pikesquares user and group
            # sudo useradd pikesquares --user-group --home-dir /var/lib/pikesquares
            console.error("could not locate `pikesquares` group. Please create one to continue.")
            raise typer.Abort() from None

    # context = services.init_context(ctx.ensure_object(dict))
    context = services.init_app(ctx.ensure_object(dict))
    context["cli-style"] = console.custom_style_dope

    override_settings = {}
    try:
        await register_app_conf(context, override_settings)
    except AppConfigError as app_conf_error:
        logger.error(app_conf_error)
        console.error("invalid config. giving up.")
        raise typer.Abort() from None

    conf = services.get(context, AppConfig)

    if conf.SENTRY_DSN:
        sentry_sdk.init(
            str(conf.SENTRY_DSN),
            send_default_pii=True,
            max_request_body_size="always",
            # Setting up the release is highly recommended. The SDK will try to
            # infer it, but explicitly setting it is more reliable:
            # release=...,
            traces_sample_rate=0,
        )

    sessionmanager = DatabaseSessionManager(conf.SQLALCHEMY_DATABASE_URI, {"echo": False})

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
    uow = await services.aget(context, UnitOfWork)

    services.register_factory(
        context,
        pluggy.PluginManager,
        plugin_manager_factory,
    )

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

    async with uow:
        try:
            machine_id = await ServiceBase.read_machine_id()
            device = await uow.devices.get_by_machine_id(machine_id)
            if not device:
                device = await provision_device(
                    uow,
                    create_kwargs={
                        "data_dir": str(conf.data_dir),
                        "config_dir": str(conf.config_dir),
                        "log_dir": str(conf.log_dir),
                        "run_dir": str(conf.run_dir),
                    },
                )
                zmq_monitor = await create_zmq_monitor(uow, device=device)
                if not zmq_monitor.socket_address:
                    console.error("device zmq monitor socket address was not provisioned")
                    raise typer.Exit(1)
                logger.info(f"created device zmq_monitor @ {zmq_monitor.socket_address}")

            uwsgi_options = await device.awaitable_attrs.uwsgi_options
            if not uwsgi_options:
                for uwsgi_option in await device.get_uwsgi_options():
                    await uow.uwsgi_options.add(uwsgi_option)

        except Exception as exc:
            logger.exception(exc)
            console.error("device was not created")
            await uow.rollback()
            raise typer.Exit(1) from None
        else:
            await uow.commit()

    # pc = services.get(context, ProcessCompose)
    await register_process_compose(context, device.machine_id, uow)

    @atexit.register
    def cleanup():
        # logger.debug("CLEANUP")
        services.close_registry(context)


# def circus_arbiter_factory():
#    watchers = []
#    check_delay = 5
#    endpoint = "tcp://127.0.0.1:5555"
#    pubsub_endpoint = "tcp://127.0.0.1:5556"
#    stats_endpoint = "tcp://127.0.0.1:5557"

#    return Arbiter(
#        watchers,
#        endpoint=endpoint,
#        pubsub_endpoint=pubsub_endpoint,
#        stats_endpoint=stats_endpoint,
#        check_delay = check_delay,
#    )
# services.register_factory(context, Arbiter, get_arbiter)
# obj["device-handler"] = device_handler

# console.info(device_handler.svc_model.model_dump())
# getattr(
#    console,
#    f"custom_style_{cli_style}",
#    getattr(console, f"custom_style_{conf.CLI_STYLE}"),
# )
