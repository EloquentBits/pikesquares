import asyncio
import atexit
import grp
import logging
import os
import shutil

# import pwd
import tempfile
from functools import wraps
from pathlib import Path
from typing import Annotated, Optional

import anyio
import cuid
import git
import giturlparse

#from sqlalchemy.sql import text
import questionary
import randomname
import sentry_sdk
import structlog
import typer
from aiopath import AsyncPath
from dotenv import load_dotenv
from plumbum import ProcessExecutionError
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    Progress,
)
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares import __app_name__, __version__, services
from pikesquares.adapters.database import DatabaseSessionManager
from pikesquares.cli.console import (
    HeaderDjangoChecks,
    HeaderDjangoSettings,
    make_layout,
    make_progress,
)

# from circus import Arbiter, get_arbiter
from pikesquares.conf import (
    AppConfig,
    AppConfigError,
    register_app_conf,
)

# from pikesquares.cli.commands.apps.validators import NameValidator
from pikesquares.domain.base import ServiceBase
from pikesquares.domain.caddy import register_caddy_process
from pikesquares.domain.device import register_device_stats
from pikesquares.domain.process_compose import (
    PCAPIUnavailableError,
    ProcessCompose,
    ServiceUnavailableError,
    register_api_process,
    register_device_process,
    register_dnsmasq_process,
    register_process_compose,
)
from pikesquares.exceptions import StatsReadError
from pikesquares.service_layer.handlers.attached_daemon import (
    attached_daemon_up,
    provision_attached_daemon,
)
from pikesquares.service_layer.handlers.device import provision_device

from pikesquares.service_layer.handlers.monitors import create_zmq_monitor
from pikesquares.service_layer.handlers.project import project_up, provision_project
from pikesquares.service_layer.handlers.routers import http_router_up
from pikesquares.service_layer.handlers.wsgi_app import provision_wsgi_app
from pikesquares.service_layer.handlers.wsgi_app import up as wsgi_app_up
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.services.apps.django import PythonRuntimeDjango
from pikesquares.services.apps.exceptions import (
    # PythonRuntimeCheckError,
    # PythonRuntimeDjangoCheckError,
    # UvCommandExecutionError,
    # PythonRuntimeInitError,
    DjangoCheckError,
    DjangoDiffSettingsError,
    #DjangoSettingsError,
    UvPipInstallError,
    UvPipListError,
    UvSyncError,
)

# from pikesquares.services.apps import RubyRuntime, PHPRuntime
from pikesquares.services.apps.python import PythonRuntime

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

# imported_module_logger = logging.getLogger("svsc")
# imported_module_logger.setLevel(logging.WARNING)
svcs_logger = logging.getLogger("svcs")
svcs_logger.setLevel(logging.WARNING)

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

load_dotenv()

app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_short=False,
    pretty_exceptions_show_locals=False,
)


def run_async(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        async def coro_wrapper():
            return await func(*args, **kwargs)

        return anyio.run(coro_wrapper)

    return wrapper


@app.command(rich_help_panel="Control", short_help="Reset device")
def reset(
    ctx: typer.Context,
    shutdown: Optional[str] = typer.Option("", "--shutdown", help="Shutdown PikeSquares server after reset."),
):
    """Reset PikeSquares Installation"""

    is_root: bool = os.getuid() == 0
    if not is_root:
        console.info("Please attempt to reset the installation as root user.")
        raise typer.Exit()

    if not questionary.confirm("Reset PikeSquares Installation?").ask():
        raise typer.Exit()

    context = ctx.ensure_object(dict)
    device = context.get("device")
    if not device:
        raise typer.Exit()

    if all(
        [
            device.get_service_status() == "running",
            shutdown or questionary.confirm("Shutdown PikeSquares Server").ask(),
        ]
    ):
        # device.stop()
        # down(ctx)
        pass

    if questionary.confirm("Drop db tables?").ask():
        # device.drop_db_tables()
        console.info("dropped db")

    if questionary.confirm("Delete all configs and logs?").ask():
        # device.delete_configs()
        console.info("deleted configs and logs")


@app.command(rich_help_panel="Control", short_help="Nuke installation")
def uninstall(ctx: typer.Context, dry_run: bool = typer.Option(False, help="Uninstall dry run")):
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


@app.command(rich_help_panel="Control", short_help="Attach to the PikeSquares Server")
def attach(
    ctx: typer.Context,
):
    """Attach to PikeSquares Server"""
    context = ctx.ensure_object(dict)
    pc = services.get(context, ProcessCompose)
    pc.attach()

@app.command(rich_help_panel="Control", short_help="Launch a preconfigured app")
@run_async
async def launch(
    ctx: typer.Context,
):
    """Launch a preconfigured app """

    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)
    uow = await services.aget(context, UnitOfWork)
    custom_style = context.get("cli-style")

    #try:
    #    vassal_stats = next(filter(lambda v: v.id.split(".ini")[0], device_stats.vassals))
    #    print(vassal_stats)
    #except StopIteration:
    #    project_zmq_monitor = await uow.zmq_monitors.get_by_project_id(project.id)
    #    vassals_home = project_zmq_monitor.uwsgi_zmq_address
    #    await project.up(device_zmq_monitor, vassals_home, tuntap_router)

    if 0:
        async with uow:
            attached_daemons = await uow.attached_daemons.list()
            for daemon in attached_daemons:
                logger.info(daemon)

            daemon_q = questionary.checkbox(
                "Select daemon: ",
                choices=[d.service_id for d in attached_daemons],
                style=custom_style,
            )
            daemon = await daemon_q.ask_async()
            print(daemon)

    def git_clone(repo_url: str, clone_into_dir: Path):
        class CloneProgress(git.RemoteProgress):
            def update(self, op_code, cur_count, max_count=None, message=""):
                # console.info(f"{op_code=} {cur_count=} {max_count=} {message=}")
                if message:
                    console.info(f"Completed git clone {message}")

        clone_into_dir.mkdir(exist_ok=True)
        if not any(clone_into_dir.iterdir()):
            try:
                return git.Repo.clone_from(repo_url, clone_into_dir,  progress=CloneProgress())
            except git.GitCommandError as exc:
                logger.exception(exc)
            # if "already exists and is not an empty directory" in exc.stderr:
                pass

    repo_url = "https://github.com/bugsink/bugsink.git"
    giturl = giturlparse.parse(repo_url)
    app_name = giturl.name
    app_root_dir = AsyncPath(conf.pyapps_dir) / app_name
    await app_root_dir.mkdir(exist_ok=True)
    app_repo_dir = AsyncPath(conf.pyapps_dir) / app_name / app_name
    app_pyvenv_dir = app_repo_dir / ".venv"
    try:
        repo = git_clone(repo_url, Path(app_repo_dir))
    except Exception as exc:
        logger.exception(exc)
        console.error(f"unable to clone {app_name} repo from {repo_url}")
        raise typer.Exit(1) from None

    project_name = app_name
    async with uow:
        try:
            machine_id = await ServiceBase.read_machine_id()
            device = await uow.devices.get_by_machine_id(machine_id)
            project = await uow.projects.get_by_name(project_name) or \
                await provision_project(project_name, device, uow)
            project_up_result = await project_up(project)
            if not project_up_result:
                console.error(f"unable to launch {project.name}")
                raise typer.Exit(1)

            http_routers = await project.awaitable_attrs.http_routers
            for http_router in http_routers:
                await http_router_up(uow, http_router)

            if 1: #attached_daemon:
                #attached_daemon_name = "redis"
                attached_daemon_name = "postgres"
                attached_daemon_bind_port = None
                attached_daemon_bind_ip = None

                attached_daemon = await provision_attached_daemon(
                    attached_daemon_name, project, uow,
                )
                attached_daemon_device = await uow.tuntap_devices.\
                    get_by_linked_service_id(attached_daemon.service_id)

                await attached_daemon_up(
                    uow,
                    attached_daemon,
                    bind_ip=attached_daemon_bind_ip,
                    bind_port=attached_daemon_bind_port,
                )
                if 0:
                    if attached_daemon.ping("/usr/local/bin/redis-cli", attached_daemon_device.ip):
                        console.success(f":heavy_check_mark:     Launching attached daemon [{attached_daemon_name}]. Done!")
                    else:
                        console.error(f"{attached_daemon_name} ping failed.")

            wsgi_app = await provision_wsgi_app(
                app_name,
                app_root_dir,
                app_repo_dir,
                app_pyvenv_dir,
                conf.UV_BIN,
                uow,
                project,
            )

            await wsgi_app_up(uow, wsgi_app, project, http_routers[0], console)

        except Exception as exc:
            logger.exception(exc)
            await uow.rollback()
            raise typer.Exit(1) from None
        else:
            await uow.commit()


@app.command(rich_help_panel="Control", short_help="Info on the PikeSquares Server")
@run_async
async def info(
    ctx: typer.Context,
):
    """Info on the PikeSquares Server"""
    context = ctx.ensure_object(dict)
    process_compose = await services.aget(context, ProcessCompose)
    processes = [
        ("device", "device manager"),
        ("caddy", "reverse proxy"),
        ("dnsmasq", "dns server"),
        ("api", "PikeSquares API"),
    ]
    for process in processes:
        try:
            stats = await process_compose.ping_api(process[0])
            logger.debug(f"{process[0]} {stats=}")
            if stats.status == "Running":
                pass
                #console.success(f":heavy_check_mark:     {process[1]} \[process-compose] is running.")
            elif stats.status == "Completed":
                pass
                #console.warning(f":heavy_exclamation_mark:     {process[1]} \[process-compose] is not running.")
        except PCAPIUnavailableError:
            console.warning(f":heavy_exclamation_mark:     Process Compose is not running.")
            break

    for svc in services.get_pings(context):
        logger.debug(f"pinging {svc.name=}")
        # pikesquares.domain.process_compose.DNSMASQProcess
        svc_name = svc.name.split(".")[-1]
        try:
            await svc.aping()
            #console.success(f":heavy_check_mark:     {svc_name} \[svcs] is running")
        except ServiceUnavailableError:
            console.warning(f":heavy_exclamation_mark:     {svc_name} is not running.")


@app.command(rich_help_panel="Control", short_help="Launch the PikeSquares Server (if stopped)")
@run_async
async def up(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """Launch PikeSquares Server"""

    context = ctx.ensure_object(dict)

    conf = await services.aget(context, AppConfig)
    process_compose = await services.aget(context, ProcessCompose)

    if conf and not conf.pyapps_dir.exists():
        logger.error(f"python apps directory @ {conf.pyapps_dir} is not available")
        raise typer.Exit(code=1) from None

    if conf and not conf.attached_daemons_dir.exists():
        logger.error(f"attached daemons directory @ {conf.attached_daemons_dir} is not available")
        raise typer.Exit(code=1) from None

    up_result = await process_compose.up()
    if not up_result:
        console.warning(":heavy_exclamation_mark:      PikeSquares Server was unable to launch")
        raise typer.Exit(code=0) from None

    #######################
    # process-compose processes
    #
    #    caddy, dnsmasq, device, api
    #
    try:
        for name, process, messages in zip(
            process_compose.config.processes.keys(),
            process_compose.config.processes.values(),
            process_compose.config.custom_messages.values(),
            strict=True,
        ):
            try:
                console.success(f"{messages.title_start} {process.description}")
                process_stats = await process_compose.ping_api(name)
                if process_stats.is_running and process_stats.status == "Running":
                    console.success(f":heavy_check_mark:     {process.description}... Launched!")
                else:
                    console.warning(f":heavy_exclamation_mark:     {process.description} unable to launch.")
            except PCAPIUnavailableError:
                await asyncio.sleep(1)
                continue

    except (StopIteration, IndexError):
        pass

    #######################
    # emperor zeromq monitors
    uow = await services.aget(context, UnitOfWork)
    machine_id = await ServiceBase.read_machine_id()
    device = await uow.devices.get_by_machine_id(machine_id)
    if not device:
        console.error(f"unable to locate device by machine id {machine_id}")
        raise typer.Exit(code=0) from None

    async with uow:
        projects = await device.awaitable_attrs.projects
        for project in projects:
            try:
                project_up_result = await project_up(project)
                if project_up_result:
                    console.success(f":heavy_check_mark:     Launching project [{project.name}]. Done!")
            except Exception as exc:
                logger.exception(exc)
                console.error(f"unable to launch {project.name}")
                continue
            project_http_routers = await project.awaitable_attrs.http_routers
            for http_router in project_http_routers:
                http_router_up_result = await http_router_up(uow, http_router)
                if http_router_up_result:
                    console.success(":heavy_check_mark:     Launching http router.. Done!")
                    console.success(":heavy_check_mark:     Launching http router subscription server.. Done!")

    console.success()
    console.success("PikeSquares API is available at: http://127.0.0.1:9000")
    console.success()
    console.success("Next steps: cd to your project directory and run `pikesquares init`")
    console.success()
    console.success("🚀 PikeSquares Server is up and running. 🚀")


@app.command(rich_help_panel="Control", short_help="Stop the PikeSquares Server (if running)")
@run_async
async def down(
    ctx: typer.Context,
):
    """Stop the PikeSquares Server"""

    context = ctx.ensure_object(dict)
    pc = await services.aget(context, ProcessCompose)
    try:
        retcode, stdout, stderr = await pc.down()
        if retcode != 0:
            console.log(retcode, stdout, stderr)
            raise typer.Exit(code=1) from None
        elif retcode == 0:
            console.success("🚀 PikeSquares Server has been shut down.")
    except ProcessExecutionError as process_exec_error:
        console.error(process_exec_error)
        console.error("PikeSquares Server was unable to shut down.")
        raise typer.Exit(code=1) from None
    except PCAPIUnavailableError:
        console.info("🚀 PikeSquares Server is not running at the moment.")
        raise typer.Exit(code=0) from None

    # try:
    #    pc.ping()
    #    console.info("Shutting down PikeSquares Server.")
    #    pc.down()
    # except process_compose.PCAPIUnavailableError:
    #    pass
    # except process_compose.PCDeviceUnavailableError:
    #    pass  # device.up()


@app.command(rich_help_panel="Control", short_help="Initialize a project")
@run_async
async def init(
    ctx: typer.Context,
    app_root_dir: Annotated[
        AsyncPath | None,
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
        ),
    ] = None,
):
    """Initialize a project"""
    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    conf = services.get(context, AppConfig)
    default_project = context.get("default-project")
    uow = await services.aget(context, UnitOfWork)
    # db = services.get(context, TinyDB)

    # uv init djangotutorial
    # cd djangotutorial
    # uv add django
    # uv run django-admin startproject mysite djangotutorial

    # https://github.com/kolosochok/django-ecommerce
    # https://github.com/healthchecks/healthchecks

    if not app_root_dir:
        current_dir = await AsyncPath().cwd()
        app_root_dir = AsyncPath(
            await questionary.path(
                "Enter the location of your project/app root directory:",
                default=str(current_dir),
                only_directories=True,
                style=custom_style,
            ).ask_async()
        )

    if not await AsyncPath(app_root_dir).exists():
        console.warning(f"Project root directory does not exist: {str(app_root_dir)}")
        raise typer.Exit(code=1)

    logger.info(f"{app_root_dir=}")

    # from contextlib import contextmanager
    # BEAT_TIME = 0.04
    # @contextmanager
    # def beat(length: int = 1) -> None:
    #     yield
    #     time.sleep(length * BEAT_TIME)

    # for runtime_class in (PythonRuntime, RubyRuntime, PHPRuntime):
    #    if runtime_class == PythonRuntime:

    runtime_base = PythonRuntime
    service_type = "WSGI-App"
    service_type_prefix = service_type.replace("-", "_").lower()
    service_id = f"{service_type_prefix}-{cuid.slug()}"
    # proj_type = "Python"
    app_path = "/home/jvved/dev/pikesquares-app-templates/django/bugsink"
    app_name = randomname.get_name().lower()
    project_name = "bugsink"
    project = await uow.projects.get_by_name(project_name)
    app_repo_dir = AsyncPath(conf.pyapps_dir) / app_name / app_name
    # pyvenv_dir = conf.pyvenvs_dir / service_id
    app_pyvenv_dir = app_repo_dir / ".venv"

    """
        jobs
            1) detect runtime
            2) detect runtime version
            3) detect framework
            4) detect dependencies
            5) validate dependencies
    """
    py_kwargs = {
        "app_root_dir": app_root_dir,
        "uv_bin": conf.UV_BIN,
        "app_repo_dir": app_repo_dir,
        "app_pyvenv_dir": app_pyvenv_dir,
        # "rich_live": live,
    }
    # console.info(py_kwargs)

    if PythonRuntime.is_django(app_root_dir):
        runtime = PythonRuntimeDjango(**py_kwargs)
        py_framework_name = "Django"
    else:
        runtime = runtime_base(**py_kwargs)
        py_framework_name = "No"

    # [link=https://www.willmcgugan.com]blog[/link]

    # text_column = TextColumn("{task.description}", table_column=Column(ratio=1))
    # bar_column = BarColumn(bar_width=None, table_column=Column(ratio=2))

    progress = make_progress()

    detect_runtime_task = progress.add_task(
        "Detecting language runtime",
        visible=True,
        total=1,
        start=False,
        emoji_fld=runtime.runtime_emoji,
        result_mark_fld="",
        description_done=f"Python {runtime.version} detected",
    )
    detect_framework_task = progress.add_task(
        "Detecting web framework",
        visible=False,
        total=1,
        start=False,
        emoji_fld=getattr(runtime, "framework_emoji", runtime.runtime_emoji),
        result_mark_fld="",
        description_done=f"{py_framework_name} framework detected",
    )
    ####################################
    #   create tmp dir
    #   copy project into tmp dir
    #   create venv in the tmp dir
    #   install dependencies into tmp dir
    #   django run check in the tmp dir
    #   django run diffsettings in the tmp dir
    #
    #   create venv in the pyvenv_dir
    #        pyvenv_dir = conf.data_dir / "venvs" / service_id
    #   install dependencies into pyvenv_dir

    detect_dependencies_task = progress.add_task(
        "Detecting project dependencies",
        visible=False,
        total=1,
        start=False,
        emoji_fld=":package:",
        result_mark_fld="",
        description_done=None,
    )

    if 0:
        for task in runtime.get_tasks():
            task_id = progress.add_task(
                task.description,
                visible=task.visible,
                total=task.total,
                start=task.start,
                emoji_fld=task.emoji_fld,
                result_mark_fld=task.result_mark_fld,
                description_done=task.description_done,
            )

    django_check_task = progress.add_task(
        "Running Django check",
        visible=False,
        total=1,
        start=False,
        emoji_fld=getattr(runtime, "framework_emoji", runtime.runtime_emoji),
        result_mark_fld="",
        description_done="Django check passed",
    )

    django_diffsettings_task = progress.add_task(
        "Django discovering modules",
        visible=False,
        total=1,
        start=False,
        emoji_fld=getattr(runtime, "framework_emoji", runtime.runtime_emoji),
        result_mark_fld="",
        description_done="Django modules discovered",
    )

    install_dependencies_task = progress.add_task(
        "Installing project dependencies",
        visible=False,
        total=1,
        start=False,
        emoji_fld=":package:",
        result_mark_fld="",
        description_done=None,
    )

    overall_progress = Progress()
    overall_task = overall_progress.add_task("All Jobs", total=int(len(progress.tasks)))

    app_tmp_dir = None
    dependencies_count = 0

    layout = make_layout()
    layout["tasks"].update(
        Panel(
            progress,
            title="Initializing Project",
            border_style="green",
            padding=(2, 2),
        ),
    )
    layout["overall_progress"].update(
        Panel(
            overall_progress,
            title="Overall Progress",
            border_style="green",
            padding=(1, 1),
        ),
    )
    layout["task_messages"].update(
        Panel(
            "",
            title="Messages",
            border_style="green",
            padding=(2, 2),
        )
    )

    task_messages_layout = layout["task_messages"]
    msg_id_styles = {
        "C": "red",
        "E": "red",
        "W": "yellow",
        "I": "green",
        "D": "green",
    }
    with Live(layout, console=console, auto_refresh=True) as live:
        while not overall_progress.finished:
            await asyncio.sleep(0.1)
            for task in progress.tasks:
                if not task.finished:
                    if task.id == detect_dependencies_task:
                        ####################################

                        # asynctempfile

                        app_tmp_dir = AsyncPath(tempfile.mkdtemp(prefix="pikesquares_", suffix="_py_app"))
                        shutil.copytree(
                            runtime.app_root_dir,
                            app_tmp_dir,
                            dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(*list(runtime.PY_IGNORE_PATTERNS)),
                        )
                        # for p in AsyncPath(app_tmp_dir).iterdir():
                        #    logger.debug(p)

                    if task.id < 2:
                        progress.start_task(task.id)
                        await asyncio.sleep(0.5)
                        progress.update(
                            task.id,
                            completed=1,
                            visible=True,
                            refresh=True,
                            description=task.fields.get("description_done", "N/A"),
                            emoji_fld=task.fields.get("emoji_fld", "N/A"),
                            result_mark_fld=":heavy_check_mark:",
                        )
                        if task.id == detect_runtime_task:
                            update_job_id = detect_framework_task
                        else:
                            update_job_id = task.id + 1
                        try:
                            progress.update(
                                update_job_id,
                                visible=True,
                                refresh=True,
                            )
                        except KeyError:
                            pass
                    else:
                        progress.update(task.id, visible=True, refresh=True)
                        progress.start_task(task.id)
                        await asyncio.sleep(0.5)

                    description_done = None

                    if task.id == detect_dependencies_task:
                        ####################################
                        # Detect Project Dependencies
                        cmd_env = {}
                        runtime.create_venv(venv=app_tmp_dir / ".venv", cmd_env=cmd_env)
                        try:
                            runtime.install_dependencies(venv=app_tmp_dir / ".venv", app_tmp_dir=app_tmp_dir)
                        except (UvSyncError, UvPipInstallError):
                            logger.error("installing dependencies failed.")
                            runtime.check_cleanup(app_tmp_dir)

                        try:
                            dependencies_count = len(runtime.dependencies_list())
                            description_done = f"{dependencies_count} dependencies detected"
                        except UvPipListError as exc:
                            logger.error(exc)
                            raise typer.Exit(1) from None

                    elif task.id == django_check_task:
                        ###################################
                        # if Django - run mange.py check
                        try:
                            runtime.collected_project_metadata["django_check_messages"] = runtime.django_check(
                                app_tmp_dir=app_tmp_dir
                            )
                            dj_msgs = runtime.collected_project_metadata.get("django_check_messages")
                            task_messages_layout.add_split(Layout(name="dj-check-msgs-header", ratio=1, size=None))
                            task_messages_layout["dj-check-msgs-header"].update(HeaderDjangoChecks())
                            for idx, msg in enumerate(dj_msgs.messages):
                                task_messages_layout.add_split(Layout(name=f"dj-msg-{idx}", ratio=1, size=None))
                                msg_id_style = msg_id_styles.get(msg.id.split(".")[-1][0])
                                task_messages_layout[f"dj-msg-{idx}"].update(
                                    Panel(
                                        f"[{msg_id_style}]{msg.id}[/{msg_id_style}] - {msg.message}",
                                        border_style="green",
                                    )
                                )
                        except DjangoCheckError:
                            if app_tmp_dir:
                                runtime.check_cleanup(app_tmp_dir)
                            # raise PythonRuntimeDjangoCheckError("django check command failed")
                    elif task.id == django_diffsettings_task:
                        ###################################
                        # if Django - run diffsettings
                        try:
                            runtime.collected_project_metadata["django_settings"] = runtime.django_diffsettings(
                                app_tmp_dir=app_tmp_dir
                            )
                            dj_settings = runtime.collected_project_metadata.get("django_settings")
                            task_messages_layout.add_split(Layout(name="dj-settings-header", ratio=1, size=None))
                            task_messages_layout["dj-settings-header"].update(HeaderDjangoSettings())
                            for msg_index, settings_fld in enumerate(dj_settings.settings_with_titles()):
                                task_messages_layout.add_split(
                                    Layout(name=f"dj-settings-msg-{msg_index}", ratio=1, size=None)
                                )
                                task_messages_layout[f"dj-settings-msg-{msg_index}"].update(
                                    Panel(
                                        f"{settings_fld[0]} - {settings_fld[1]}\n",
                                        border_style="green",
                                    )
                                )
                        except DjangoDiffSettingsError:
                            if app_tmp_dir:
                                runtime.check_cleanup(app_tmp_dir)
                            # raise PythonRuntimeDjangoCheckError("django diffsettings command failed.")
                    elif task.id == install_dependencies_task:
                        ####################################
                        # Installing Project Dependencies
                        cmd_env = {
                            # "UV_CACHE_DIR": str(conf.pv_cache_dir),
                            "UV_PROJECT_ENVIRONMENT": str(pyvenv_dir),
                        }
                        runtime.create_venv(pyvenv_dir, cmd_env=cmd_env)
                        runtime.install_dependencies()
                        description_done = f"{dependencies_count} dependencies installed"

                    progress.update(
                        task.id,
                        completed=1,
                        visible=True,
                        refresh=True,
                        description=description_done or task.fields.get("description_done"),
                        emoji_fld=task.fields.get("emoji_fld", "N/A"),
                        result_mark_fld=":heavy_check_mark:",
                    )
                    completed = sum(task.completed for task in progress.tasks)
                    overall_progress.update(overall_task, completed=completed)

        # app_name = questionary.text(
        #    "Choose a name for your app: ",
        #    default=randomname.get_name().lower(),
        #    style=custom_style,
        #    validate=NameValidator,
        # ).ask()
        # console_status.update(status="[magenta]Provisioning Python app", spinner="earth")

        # app_project = services.get(context, SandboxProject)
        """
        try:
            wsgi_app = runtime.get_app(
                conf,
                # db,
                app_name,
                service_id,
                # app_project,
                pyvenv_dir,
                # build_routers(app_name),
            )
            logger.info(wsgi_app.config_json)
        except DjangoSettingsError:
            logger.error("[pikesquares] -- DjangoSettingsError --")
            raise typer.Exit() from None
        """


        uwsgi_plugins = ["tuntap"]
        async with uow:
            wsgi_app = await provision_wsgi_app(
                app_name,
                app_root_dir,
                app_repo_dir,
                app_pyvenv_dir,
                conf.UV_BIN,
                uow,
                project,
            )
        if default_project:
            # proj_zmq_addr = f"{default_project.monitor_zmq_ip}:{default_project.monitor_zmq_port}"
            await wsgi_app.zmq_monitor_create_instance()
            console.success(f":heavy_check_mark:     Launching wsgi app {app_name}.. Done!")
            console.print("[bold green]WSGI App has been provisioned.")

    # console.log(runtime.collected_project_metadata["django_settings"])
    # console.log(runtime.collected_project_metadata["django_check_messages"])
    # console.log(wsgi_app.config_json)


@app.command(rich_help_panel="Control", short_help="tail the service log")
def tail_service_log(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """ """

    obj = ctx.ensure_object(dict)
    obj["cli-style"] = console.custom_style_dope

    # device = services.get(obj, Device)
    # show_config_start_marker = ";uWSGI instance configuration\n"
    # show_config_end_marker = ";end of configuration\n"

    # latest_running_config, latest_startup_log = device.startup_log(
    #     show_config_start_marker, show_config_end_marker
    # )
    # for line in latest_running_config:
    #     console.info(line)

    # for line in latest_startup_log:
    #     console.info(line)


from .commands import apps, devices, managed_services, projects, routers

app.add_typer(apps.app, name="apps")
app.add_typer(routers.app, name="routers")
app.add_typer(projects.app, name="projects")
app.add_typer(devices.app, name="devices")
# app.add_typer(managed_services.app, name="services")


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

    logger.info(f"About to execute command: {ctx.invoked_subcommand}")
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
        else:
            # continue running as `pikesquares` group
            try:
                os.setgid(grp.getgrnam("pikesquares")[2])
            except IndexError:
                # TODO
                # create pikesquares user and group
                # sudo useradd pikesquares --user-group --home-dir /var/lib/pikesquares
                console.error("could not locate `pikesquares` group. Please create one to continue.")
                raise typer.Abort() from None
                # os.setgid(grp.getgrnam("pikesquares")[2])

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

    sessionmanager = DatabaseSessionManager(
        conf.SQLALCHEMY_DATABASE_URI,
        {"echo": False}
    )

    async def get_session() -> AsyncSession:
        async with sessionmanager.session() as session:
            return session

    services.register_factory(context, AsyncSession, get_session) #ping=lambda session: session.execute(text("SELECT 1")),
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
            raise typer.Exit(1)
        else:
            await uow.commit()

    await register_device_process(context, device.machine_id)
    await register_api_process(context)
    await register_dnsmasq_process(context)
    await register_caddy_process(context)
    await register_device_stats(context)
    await register_process_compose(context)

    # pc = services.get(context, ProcessCompose)

    @atexit.register
    def cleanup():
        logger.debug("CLEANUP")
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
