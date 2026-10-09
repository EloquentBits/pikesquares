import atexit
import grp
import logging
import os
import sys
import sysconfig
from pathlib import Path
from typing import Annotated

import sentry_sdk

# import structlog
import structlog_sentry_logger
import typer
from dotenv import load_dotenv

from pikesquares import __app_name__, __version__, services
from pikesquares.conf import (
    AppConfig,
    AppConfigError,
    register_app_conf,
)
from pikesquares.services.init import init_db, init_device, init_pluggy, init_process_compose

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
for import_lib in [
    "svcs",
    "asyncio",
    "aiosqlite",
    # "plumbum"
]:
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


from .commands import apps, build, control, devices, managed_services, projects, routers

app.add_typer(control.app)
app.add_typer(apps.app, name="apps")
app.add_typer(routers.app, name="routers")
app.add_typer(projects.app, name="projects")
app.add_typer(devices.app, name="devices")
app.add_typer(managed_services.app, name="services")
app.add_typer(build.app, name="build")


def _version_callback(value: bool) -> None:
    if value:
        console.info(f"{__app_name__} v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
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
    #
    run_foreground = True

    is_root: bool = os.getuid() == 0
    platform = sys.platform
    if platform == "darwin":
        platform = "macos"
    elif platform.startswith("linux"):
        platform = "linux"
    else:
        console.error(f"unsupported platform {platform}")
        raise typer.Exit(1)

    # FIXME make sure to make an exception for --help
    if ctx.invoked_subcommand in set(
        {
            "up",
            "down",
        }
    ):
        if 0:
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
    context["run_foreground"] = run_foreground
    override_settings = {}

    # check if locally built uwsgi binary is available
    # uwsgi_bin_local = Path("/var/lib/pikesquares/scie-pikesquares/uwsgi/uwsgi")
    # if uwsgi_bin_local.exists():
    #    override_settings = {"UWSGI_BIN": uwsgi_bin_local}
    try:
        register_app_conf(context, override_settings)
    except AppConfigError as app_conf_error:
        logger.error(app_conf_error)
        console.error("invalid config. giving up.")
        raise typer.Abort() from None

    init_db(context)

    conf = services.get(context, AppConfig)

    if ctx.invoked_subcommand == "up":
        # include_dir = Path(sysconfig.get_path("include"))
        # if include_dir is None:
        #    raise typer.Exit(1)

        # do this only before building the Python plugin
        if 0:
            if not (include_dir / "Python.h").exists():
                inc = sysconfig.get_path("include")
                console.warning("Python development header files are not installed.")
                console.warning(f"Checked path: {os.path.join(inc, 'Python.h') if inc else 'N/A'}")
                if platform == "linux":
                    console.info("install python3-dev package. i.e. sudo apt install python3-dev")
                elif platform == "macos":
                    console.info("install python3-dev package. i.e. brew install python3-dev")
                raise typer.Exit(1)

        build.build_uwsgi_deps(conf)

    device = init_device(context)

    if not run_foreground:
        init_process_compose(context, device)

    init_pluggy(context)

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
