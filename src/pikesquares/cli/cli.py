import sys
import os
import traceback
import time
from typing import Optional, Annotated, NewType
from pathlib import Path

import randomname
import typer
import questionary
from tinydb import TinyDB, Query
from cuid import cuid
from dotenv import load_dotenv

#from circus import Arbiter, get_arbiter

from pikesquares.conf import (
    AppConfig,
    AppConfigError,
    register_app_conf,
    SysDir,
    make_system_dir,
)
from pikesquares import services
from pikesquares.services.base import StatsReadError
from pikesquares.services.device import Device, register_device
from pikesquares.services.project import (
    SandboxProject,
    Project,
    register_sandbox_project,
)
from pikesquares.services.router import (
    HttpsRouter,
    HttpRouter,
    DefaultHttpsRouter,
    DefaultHttpRouter,
    register_router,
)
from pikesquares.services import process_compose
from pikesquares.services.apps import RubyRuntime, PHPRuntime
from pikesquares.services.apps.python import PythonRuntime
from pikesquares.services.apps.django import PythonRuntimeDjango
from pikesquares.cli.commands.apps.validators import NameValidator

from pikesquares.services.apps.django import (
    DjangoWsgiApp,
)
from pikesquares.services.apps.exceptions import (
    PythonRuntimeInitError,
)

from pikesquares.services.data import (
#    RouterStats,
    Router,
 )
# from ..services.router import *
# from ..services.app import *

from .console import console
from pikesquares import __app_name__, __version__, get_first_available_port

load_dotenv()

app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_short=False,
    pretty_exceptions_show_locals=True,
)


@app.command(rich_help_panel="Control", short_help="Reset device")
def reset(
    ctx: typer.Context,
    shutdown: Optional[str] = typer.Option(
        "",
        "--shutdown",
        help="Shutdown PikeSquares server after reset."
    ),
):
    """Reset PikeSquares Installation"""

    context = ctx.ensure_object(dict)
    device = services.get(context, Device)

    if not questionary.confirm("Reset PikeSquares Installation?").ask():
        raise typer.Exit()

    if all(
        [
            device.get_service_status() == "running",
            shutdown or questionary.confirm("Shutdown PikeSquares Server").ask(),
        ]
    ):
        device.stop()
        console.success("PikeSquares Server has been shut down.")

    if questionary.confirm("Drop db tables?").ask():
        device.drop_db_tables()

    if questionary.confirm("Delete all configs and logs?").ask():
        device.delete_configs()


@app.command(rich_help_panel="Control", short_help="Nuke installation")
def uninstall(
        ctx: typer.Context,
        dry_run: bool = typer.Option(False, help="Uninstall dry run")
    ):
    """Delete the entire PikeSquares installation"""

    context = ctx.ensure_object(dict)
    # device= services.HandlerFactory.make_handler("Device")(services.Device(service_id="device"))
    # device.uninstall(dry_run=dry_run)
    console.info("PikeSquares has been uninstalled.")


# @app.command(rich_help_panel="Control", short_help="Write to master fifo")
# def write_to_master_fifo(
#    ctx: typer.Context,
#    service_id: Annotated[str, typer.Option("--service-id", "-s", help="Service ID to send the command to")],
#    command: Annotated[str, typer.Option("--command", "-c", help="Command to send master fifo.")],
# ):
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    service_id = service_id or "device"
#    fifo_file = Path(conf.RUN_DIR) / f"{service_id}-master-fifo"
#    write_master_fifo(fifo_file, command)


# @app.command(rich_help_panel="Control", short_help="Show logs of device")
# def logs(ctx: typer.Context, entity: str = typer.Argument("device")):
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    status = get_service_status(f"{entity}-emperor", conf)

#    log_file = Path(conf.LOG_DIR) / f"{entity}.log"
#    if log_file.exists() and log_file.is_file():
#        console.pager(
#            log_file.read_text(),
#            status_bar_format=f"{log_file.resolve()} (status: {status})"
#        )


# @app.command(rich_help_panel="Control", short_help="Show status of device (running or stopped)")
# def status(ctx: typer.Context):
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    status = get_service_status(f"device", conf)
#    if status == "running":
#        log_func = console.success
#    else:
#        log_func = console.error
#    log_func(f"Device is [b]{status}[/b]")


@app.command(
         rich_help_panel="Control",
         short_help="Attach to the PikeSquares Server")
def attach(
     ctx: typer.Context,
):
    """Attach to PikeSquares Server"""
    context = ctx.ensure_object(dict)
    pc = services.get(context, process_compose.ProcessCompose)
    pc.attach()


@app.command(
        rich_help_panel="Control",
        short_help="Info on the PikeSquares Server")
def info(
    ctx: typer.Context,
):
    """Info on the PikeSquares Server"""
    context = ctx.ensure_object(dict)

    conf = services.get(context, AppConfig)
    # console.info(f"data_dir={str(conf.DATA_DIR)}")
    console.info(f"virtualenv={str(conf.VIRTUAL_ENV)}")

    device = services.get(context, Device)
    # pc = services.get(context, process_compose.ProcessCompose)
    try:
        # pc.ping_api()
        if device.stats:
            console.success("🚀 PikeSquares Server is running.")
    except StatsReadError:
        console.warning("PikeSquares Server is not running.")
    # except (process_compose.PCAPIUnavailableError,
    #        process_compose.PCDeviceUnavailableError):
    #    console.warning("PikeSquares Server is not running.")
    #    raise typer.Exit() from None

    # http_router = services.get(context, DefaultHttpRouter)
    # stats = http_router.read_stats()
    # http_router_stats = RouterStats(**stats)
    # console.info(http_router_stats.model_dump())

    # https_router = services.get(context, DefaultHttpsRouter)
    # https_router_stats = RouterStats(https_router.read_stats())
    # console.info(https_router_stats.model_dump())




@app.command(
        rich_help_panel="Control",
        short_help="Launch the PikeSquares Server (if stopped)")
def up(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """Launch PikeSquares Server"""

    # context = ctx.ensure_object(dict)
    # conf = services.get(context, conf.AppConfig)
    # nothing to do here
    pass


@app.command(rich_help_panel="Control", short_help="Stop the PikeSquares Server (if running)")
def down(
    ctx: typer.Context,
):
    """Stop the PikeSquares Server"""
    context = ctx.ensure_object(dict)
    pc = services.get(context, process_compose.ProcessCompose)
    try:
        pc.ping()
        console.info("Shutting down PikeSquares Server.")
        pc.down()
    except process_compose.PCAPIUnavailableError:
        pass
    except process_compose.PCDeviceUnavailableError:
        pass  # device.up()


@app.command(rich_help_panel="Control", short_help="Bootstrap the PikeSquares Server)")
def bootstrap(
     ctx: typer.Context,
):
    """Bootstrap the PikeSquares Server"""
    context = ctx.ensure_object(dict)
    for svc_class in [
             Device,
             SandboxProject,
             DefaultHttpsRouter,
             DefaultHttpRouter,
         ]:
        svc = services.get(context, svc_class)
        svc.up()
    console.info("bootstrap done")

    raise typer.Exit(code=0)


@app.command(
    rich_help_panel="Control",
    short_help="Initialize a project"
)
def init(
     ctx: typer.Context,
    app_root_dir: Annotated[
        Path | None,
        typer.Option(
            "--root-dir",
            "-d",
            exists=True,
            file_okay=False,
            dir_okay=True,
            writable=False,
            readable=True,
            resolve_path=True,
            help="Project/App root directory",
        )
    ] = None,
):
    """Initialize a project"""
    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    conf = services.get(context, AppConfig)
    db = services.get(context, TinyDB)

    # uv init djangotutorial
    # cd djangotutorial
    # uv add django
    # uv run django-admin startproject mysite djangotutorial

    # https://github.com/kolosochok/django-ecommerce
    # https://github.com/healthchecks/healthchecks

    app_root_dir = app_root_dir or Path(questionary.path(
        "Enter the location of your project/app root directory:",
        default=str(Path().cwd()),
        only_directories=True,
        style=custom_style,
    ).ask())

    if app_root_dir and not app_root_dir.exists():
        console.info(f"Project root directory does not exist: {str(app_root_dir)}")
        raise typer.Exit(code=1)

    print(f"{app_root_dir=}")

    for runtime_class in (PythonRuntime, RubyRuntime, PHPRuntime):
        if runtime_class == PythonRuntime:
            service_type = "WSGI-App"
            service_type_prefix = service_type.replace("-", "_").lower()
            service_id = f"{service_type_prefix}_{cuid()}"

            if PythonRuntime.is_django(app_root_dir):
                runtime = PythonRuntimeDjango(app_root_dir=app_root_dir)
            else:
                runtime = PythonRuntime(app_root_dir=app_root_dir)

            runtime.uv_bin = conf.UV_BIN
            try:
                pyvenv_dir = conf.data_dir / "venvs" / service_id
                if runtime.init(pyvenv_dir):
                    print("[pikesquares] PYTHON RUNTIME COMPLETED INIT")
                    print(runtime.model_dump())

                    app_name = questionary.text(
                        "Choose a name for your app: ",
                        default=randomname.get_name().lower(),
                        style=custom_style,
                        validate=NameValidator,
                    ).ask()

                    default_https_router = services.get(context, DefaultHttpsRouter)
                    default_http_router = services.get(context, DefaultHttpRouter)

                    https_router_kwargs = {
                        "router_id": default_https_router.service_id,
                        "subscription_server_address": default_https_router.subscription_server_address,
                        "subscription_notify_socket": default_https_router.notify_socket,
                        "app_name": app_name,
                    }
                    http_router_kwargs = {
                        "router_id": default_http_router.service_id,
                        "subscription_server_address": default_http_router.subscription_server_address,
                        "subscription_notify_socket": default_http_router.notify_socket,
                        "app_name": app_name,
                    }
                    routers = [
                        Router(**https_router_kwargs),
                        Router(**http_router_kwargs),
                    ]
                    app_project = services.get(context, SandboxProject)

                    wsgi_app = runtime.get_app(
                        conf,
                        db,
                        app_name,
                        service_id,
                        app_project,
                        pyvenv_dir,
                        routers,
                    )
                    print(wsgi_app)


            except PythonRuntimeInitError:
                print("[pikesquares] -- PythonRuntimeInitError --")
                #print(traceback.format_exc())

        elif runtime_class == RubyRuntime:
            pass
        elif runtime_class == PHPRuntime:
            pass


@app.command(rich_help_panel="Control", short_help="tail the service log")
def tail_service_log(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """ """

    obj = ctx.ensure_object(dict)
    obj["cli-style"] = console.custom_style_dope

    device = services.get(obj, Device)
    show_config_start_marker = ";uWSGI instance configuration\n"
    show_config_end_marker = ";end of configuration\n"

    latest_running_config, latest_startup_log = device.startup_log(
        show_config_start_marker, show_config_end_marker
    )
    for line in latest_running_config:
        console.info(line)

    for line in latest_startup_log:
        console.info(line)


from .commands import devices
from .commands import apps
from .commands import managed_services

app.add_typer(apps.app, name="apps")
app.add_typer(devices.app, name="devices")
app.add_typer(managed_services.app, name="services")


def _version_callback(value: bool) -> None:
    if value:
        console.info(f"{__app_name__} v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
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
            help="PikeSquares data directory",
        )
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
            help="PikeSquares configs directory",
        )
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
            help="PikeSquares logs directory",
        )
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
            help="PikeSquares run directory",
        )
    ] = None,
    # build_configs: Optional[bool] = typer.Option(
    #    False,
    #    help="Write configs to disk"
    # ),
    # disable_process_compose: Optional[bool] = typer.Option(
    #    False,
    #    help="Run without process-compose"
    # ),
) -> None:
    """
    Welcome to Pike Squares. Building blocks for your apps.
    """

    console.info(f"About to execute command: {ctx.invoked_subcommand}")
    for key, value in os.environ.items():
        if key.startswith(("PIKESQUARES", "SCIE", "PEX", "VIRTUAL_ENV")):
            print(f"{key}: {value}")

    is_root: bool = os.getuid() == 0
    print(f"{os.getuid()=} {is_root=}")

    if ctx.invoked_subcommand in set({"bootstrap", "up"}) and not is_root:
        console.info("Please start server as root user. `sudo pikesquares up`")
        raise typer.Exit()

    pikesquares_version = version or os.environ.get("PIKESQUARES_VERSION")
    if not pikesquares_version:
        console.error("Unable to read the pikesquares version")
        raise typer.Exit(1)

    #scie_base = os.environ.get("PIKESQUARES_SCIE_BASE")
    #if not scie_base:
    #    console.error("Unable to read the pikesquares scie base directory")
    #    raise typer.Exit(1)

    console.info(f"PikeSquares: v{pikesquares_version}")
    context = services.init_context(ctx.ensure_object(dict))
    print(vars(ctx))

    context = services.init_app(ctx.ensure_object(dict))
    context["cli-style"] = console.custom_style_dope

    # and not all([
    #    Path(process_compose_dir),
    #    Path(process_compose_dir).is_dir()]):
    #process_compose_dir = os.environ.get("PIKESQUARES_PROCESS_COMPOSE_DIR")
    #if not process_compose_dir:
    #    console.error(f"unable to locate process-compose directory @ {process_compose_dir}")
    #    raise typer.Abort()

    override_settings = {
        "PIKESQUARES_DATA_DIR": os.environ.get("PIKESQUARES_DATA_DIR", "/var/lib/pikesquares"),
        "PIKESQUARES_RUN_DIR": os.environ.get("PIKESQUARES_RUN_DIR", "/var/run/pikesquares"),
        "PIKESQUARES_LOG_DIR": os.environ.get("PIKESQUARES_LOG_DIR", "/var/log/pikesquares"),
        "PIKESQUARES_CONFIG_DIR": os.environ.get("PIKESQUARES_CONFIG_DIR", "/etc/pikesquares"),

    }
    if is_root:
        sysdirs = {
            "data_dir": (data_dir, os.environ.get("PIKESQUARES_DATA_DIR"), Path("/var/lib/pikesquares")),
            "run_dir": (run_dir, os.environ.get("PIKESQUARES_RUN_DIR"), Path("/var/run/pikesquares")),
            "config_dir": (config_dir, os.environ.get("PIKESQUARES_CONFIG_DIR"), Path("/etc/pikesquares")),
            "log_dir": (log_dir, os.environ.get("PIKESQUARES_LOG_DIR"), Path("/var/log/pikesquares")),
        }
        for varname, path_to_dir_sources in sysdirs.items():
            cli_arg = path_to_dir_sources[0]
            env_var_path_to_dir = path_to_dir_sources[1]
            default_path_to_dir = path_to_dir_sources[2]
            print(f"{varname=}")
            if cli_arg:
                print(f"cli args: {cli_arg}.")
            if env_var_path_to_dir:
                print(f"env var: {env_var_path_to_dir}")
            # ensure_sysdir(sysdir, varname)

            path_to_dir = cli_arg or env_var_path_to_dir or default_path_to_dir
            if isinstance(path_to_dir, str):
                path_to_dir = Path(path_to_dir)
            if not path_to_dir.exists():
                print(f"creating dir: {path_to_dir}")
                make_system_dir(path_to_dir)
            override_settings[varname] = path_to_dir

    if version:
        override_settings["VERSION"] = version

    print(f"{override_settings=}")

    try:
        register_app_conf(
            context,
            override_settings,
        )
    except AppConfigError:
        console.error(traceback.format_exc())
        # console.error(f"unable to load AppConf from {str(db_path)}")
        raise typer.Abort() from None

    conf = services.get(context, AppConfig)

    print(f"{conf.data_dir=}")
    db_path = conf.data_dir / "device-db.json"
    print(f"{db_path=}")
    services.register_db(
        context,
        db_path,
    )
    db = services.get(context, TinyDB)

    # console.info(conf.model_dump())

    build_configs = ctx.invoked_subcommand == "bootstrap"
    register_device(
        context,
        Device,
        conf,
        db,
        build_config_on_init=build_configs,
    )
    device = services.get(context, Device)

    register_sandbox_project(
        context,
        SandboxProject,
        Project,
        conf,
        db,
        build_config_on_init=build_configs,
    )
    sandbox_project = services.get(context, SandboxProject)

    router_https_address = \
        f"0.0.0.0:{str(get_first_available_port(port=8443))}"
    router_https_subscription_server_address = \
        f"127.0.0.1:{get_first_available_port(port=5600)}"

    router_http_address = "0.0.0.0:8034"
    router_http_subscription_server_address = \
        f"127.0.0.1:{get_first_available_port(port=5700)}"

    router_plugins = []
    register_router(
        context,
        router_https_address,
        router_https_subscription_server_address,
        router_plugins,
        DefaultHttpsRouter,
        HttpsRouter,
        conf,
        db,
        build_config_on_init=build_configs,
    )
    register_router(
        context,
        router_http_address,
        router_http_subscription_server_address,
        router_plugins,
        DefaultHttpRouter,
        HttpRouter,
        conf,
        db,
        build_config_on_init=build_configs,
    )
    process_compose.register_process_compose(
        context,
        conf,
        (get_first_available_port(port=9555)),

    )
    # http_router = services.get(context, DefaultHttpRouter)
    # https_router = services.get(context, DefaultHttpsRouter)

    if ctx.invoked_subcommand == "up":
        pc_api_port = 9555
        # uwsgi_bin = os.environ.get("PIKESQUARES_UWSGI_BIN")
        # if not all([uwsgi_bin, Path(uwsgi_bin).exists()]):
        #    raise Exception("unable to locate uwsgi binary @ {uwsgi_bin}")
        pc = services.get(context, process_compose.ProcessCompose)
        try:
            pc.ping()
        except process_compose.PCAPIUnavailableError:
            if ctx.invoked_subcommand == "up":
                launch_pc(pc, device)
        except process_compose.PCDeviceUnavailableError:
            pass  # device.up()
            # console.info("-- PCDeviceUnavailableError --")
            # sandbox_project.ping()
    #elif ctx.invoked_subcommand in set({"down", "bootstrap"}):
    #    return

    """
    for svc in services.get_pings(context):
        # print(f"pinging {svc.name=}")
        try:
            svc.ping()
            if ctx.invoked_subcommand == "up":
                console.info("looks like PikeSquares Server is already running.")
                console.info("try `pikesquares attach` to see running processes.")
                raise typer.Exit() from None
            elif ctx.invoked_subcommand == "down":
                console.info("Shutting down PikeSquares Server.")
                pc.down()
                raise typer.Exit() from None
        except process_compose.ServiceUnavailableError:
            console.info(f"=== {svc.name} Service Unavailable ===")
            if ctx.invoked_subcommand == "down":
                raise typer.Exit() from None

        if ctx.invoked_subcommand == "up":
            launch_pc(pc, device)
    """

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


def launch_pc(pc: process_compose.ProcessCompose, device: Device):
    with console.status("Launching the PikeSquares Server", spinner="earth"):
        pc.up()
        time.sleep(10)
        try:
            pc.ping_api()
            console.success("🚀 PikeSquares Server is running.")
        except process_compose.PCAPIUnavailableError:
            console.info("process-compose api not available.")
        except process_compose.PCDeviceUnavailableError:
            console.error("PikeSquares Server was unable to start.")
            raise typer.Exit() from None

        # if not device.get_service_status() == "running":
        #    console.warning(f"Device stats @ {device.stats_address} are unavailable.")
        #    console.error("PikeSquares Server was unable to start.")
        #    raise typer.Exit() from None


"""
@app.callback(invoke_without_command=True)
def main_bak(
    ctx: typer.Context,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose mode.")] = False,
    version: Annotated[bool, typer.Option("--version", "-V", help="Show version and exit.")] = False,
    #cli_style: Annotated[str, typer.Option("--cli-style", "-c", help="Custom CLI Style")] = "dope",
):            
"""

# from .commands.routers import *
# from .commands.projects import *

# ALIASES = ("applications", "app")
# HELP = f"""
#    Application commands.\n
#    Aliases: [i]{', '.join(ALIASES)}[/i]
# """

# apps_cmd = typer.Typer(
#    no_args_is_help=True,
#    rich_markup_mode="rich",
#    name="apps",
#    help=HELP
# )
# for alias in ALIASES:
#    app.add_typer(
#        apps_cmd,
#        name=alias,
#        help=HELP,
#        hidden=True
#    )
