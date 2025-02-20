import os
import tempfile
import shutil
import logging
from time import sleep
from typing import Optional, Annotated
from pathlib import Path

from rich.progress import (
    Progress,
    TextColumn,
    SpinnerColumn,
)
from rich.table import Column
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

import randomname
import typer
import questionary
from tinydb import TinyDB
from cuid import cuid
from dotenv import load_dotenv
from plumbum import ProcessExecutionError
import structlog
# from circus import Arbiter, get_arbiter

from pikesquares.conf import (
    AppConfig,
    AppConfigError,
    register_app_conf,
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
# from pikesquares.cli.commands.apps.validators import NameValidator
from pikesquares.services import process_compose
from pikesquares.services.apps import RubyRuntime, PHPRuntime
from pikesquares.services.apps.python import PythonRuntime
from pikesquares.services.apps.django import PythonRuntimeDjango

from pikesquares.services.apps.exceptions import (
    UvSyncError,
    UvPipInstallError,
    UvPipListError,
    # PythonRuntimeCheckError,
    # PythonRuntimeDjangoCheckError,
    # UvCommandExecutionError,
    PythonRuntimeInitError,
    DjangoCheckError,
    DjangoDiffSettingsError,
    DjangoSettingsError,
)


from pikesquares.services.data import (
#    RouterStats,
    Router,
 )
# from ..services.router import *
# from ..services.app import *

from .console import console
from pikesquares import __app_name__, __version__, get_first_available_port


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
logger.info("This message will only be written to the log file ---- CLI ---")

load_dotenv()

app = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_short=False,
    pretty_exceptions_show_locals=False,
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
    logger.debug(f"virtualenv={str(conf.PYTHON_VIRTUAL_ENV)}")

    device = services.get(context, Device)
    pc = services.get(context, process_compose.ProcessCompose)
    try:
        pc.ping_api()
        try:
            if device.stats:
                console.success("🚀 PikeSquares Server is running.")
        except StatsReadError:
            console.warning("PikeSquares Server is not running.")

    except process_compose.PCAPIUnavailableError:
        console.info("PCAPIUnavailableError: process-compose api not available.")
    except process_compose.PCDeviceUnavailableError:
        console.error("PCDeviceUnavailableError: PikeSquares Server was unable to start.")
        raise typer.Exit() from None

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

    context = ctx.ensure_object(dict)
    # conf = services.get(context, AppConfig)
    pc = services.get(context, process_compose.ProcessCompose)

    with console.status("Launching the PikeSquares Server", spinner="earth"):
        try:
            retcode, stdout, stderr = pc.up()
            if retcode != 0:
                console.log(retcode, stdout, stderr)
                raise typer.Exit(code=1) from None
            elif retcode == 0:
                for _ in range(1, 5):
                    try:
                        pc.ping_api()
                        console.success("🚀 PikeSquares Server is running.")
                        return True
                    except (
                            process_compose.PCAPIUnavailableError,
                            process_compose.PCDeviceUnavailableError
                    ):
                        sleep(1)
                        continue
                console.error("PikeSquares Server was unable to start.")
                raise typer.Exit(code=0) from None

        except ProcessExecutionError as process_exec_error:
            console.error(process_exec_error)
            console.error("PikeSquares Server was unable to start.")
            raise typer.Exit(code=1) from None

@app.command(rich_help_panel="Control", short_help="Stop the PikeSquares Server (if running)")
def down(
    ctx: typer.Context,
):
    """Stop the PikeSquares Server"""
    context = ctx.ensure_object(dict)
    pc = services.get(context, process_compose.ProcessCompose)
    try:
        retcode, stdout, stderr = pc.down()
        if retcode != 0:
            console.log(retcode, stdout, stderr)
            raise typer.Exit(code=1) from None
        elif retcode == 0:
            console.success("🚀 PikeSquares Server has been shut down.")
    except ProcessExecutionError as process_exec_error:
        console.error(process_exec_error)
        console.error("PikeSquares Server was unable to shut down.")
        raise typer.Exit(code=1) from None
    except process_compose.PCAPIUnavailableError:
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
        console.warning(f"Project root directory does not exist: {str(app_root_dir)}")
        raise typer.Exit(code=1)

    logger.info(f"{app_root_dir=}")

    def build_routers(app_name: str) -> list[Router]:

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
        return routers

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
    service_id = f"{service_type_prefix}_{cuid()}"
    proj_type = "Python"
    pyvenv_dir = conf.data_dir / "venvs" / service_id
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
        "uv_bin": conf.PYTHON_VIRTUAL_ENV / "bin/uv",
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

    class MyProgress(Progress):
        def get_renderables(self):
            yield self.make_tasks_table(self.tasks)

    progress = MyProgress(
        SpinnerColumn(),
        TextColumn("{task.fields[emoji_fld]}", table_column=Column(ratio=1)),
        TextColumn("[progress.description]{task.description}", table_column=Column(ratio=5)),
        # TextColumn("{task.fields[detected_fld]}", table_column=Column(ratio=1, style="green")),
        TextColumn("{task.fields[result_mark_fld]}", table_column=Column(ratio=1)),
        auto_refresh=False,
        console=console,
    )

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

    def make_layout():
        layout = Layout(name="root")
        layout.split(
            Layout(name="overall_progress", size=5),
            Layout(name="tasks_and_messages", size=20),
        )
        layout["tasks_and_messages"].split_row(
            Layout(name="tasks",
                ratio=2,
                size=None,
                # minimum_size=30,
            ),
            Layout(
                name="task_messages",
                ratio=3,
                size=None,
            ),
        )
        return layout

    class HeaderDjangoChecks:
        def __rich__(self) -> Panel:
            grid = Table.grid(expand=True)
            grid.add_column(justify="center", ratio=1)
            grid.add_column(justify="right")
            grid.add_row(
                "Static checks for validating Django projects",
                "Django 5.2.4",
            )
            return Panel(grid, style="white on blue")

    class HeaderDjangoSettings:
        def __rich__(self) -> Panel:
            grid = Table.grid(expand=True)
            grid.add_column(justify="center", ratio=1)
            grid.add_column(justify="right")
            grid.add_row(
                "Discovered Django settings",
                "Django 5.2.4",
            )
            return Panel(grid, style="white on blue")

    layout = make_layout()
    layout["tasks"].update(Panel(
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
    layout["task_messages"].update(Panel("", title="Messages", border_style="green", padding=(2, 2),))
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
            sleep(0.1)
            for job in progress.tasks:
                if not job.finished:
                    if job.id == detect_dependencies_task:
                        ####################################
                        app_tmp_dir = Path(
                            tempfile.mkdtemp(prefix="pikesquares_", suffix="_py_app")
                        )
                        shutil.copytree(
                            runtime.app_root_dir,
                            app_tmp_dir,
                            dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(*list(runtime.PY_IGNORE_PATTERNS))
                        )
                        for p in Path(app_tmp_dir).iterdir():
                            logger.debug(p)

                    if job.id < 2:
                        progress.start_task(job.id)
                        sleep(0.5)
                        progress.update(
                            job.id,
                            completed=1,
                            visible=True,
                            refresh=True,
                            description=job.fields.get("description_done", "N/A"),
                            emoji_fld=job.fields.get("emoji_fld", "N/A"),
                            result_mark_fld=":heavy_check_mark:"
                        )
                        if job.id == detect_runtime_task:
                            update_job_id = detect_framework_task
                        else:
                            update_job_id = job.id + 1
                        try:
                            progress.update(
                                update_job_id,
                                visible=True,
                                refresh=True,
                            )
                        except KeyError:
                            pass
                    else:
                        progress.update(job.id, visible=True, refresh=True)
                        progress.start_task(job.id)
                        sleep(0.5)

                    description_done = None

                    if job.id == detect_dependencies_task:
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

                    elif job.id == django_check_task:
                        ###################################
                        # if Django - run mange.py check
                        try:
                            runtime.collected_project_metadata["django_check_messages"] = \
                                    runtime.django_check(app_tmp_dir=app_tmp_dir)
                            dj_msgs = runtime.collected_project_metadata.get("django_check_messages")
                            task_messages_layout.add_split(
                                Layout(name="dj-check-msgs-header", ratio=1, size=None)
                            )
                            task_messages_layout["dj-check-msgs-header"].update(HeaderDjangoChecks())
                            for idx, msg in enumerate(dj_msgs.messages):
                                task_messages_layout.add_split(
                                        Layout(name=f"dj-msg-{idx}", ratio=1, size=None)
                                )
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
                    elif job.id == django_diffsettings_task:
                        ###################################
                        # if Django - run diffsettings
                        try:
                            runtime.collected_project_metadata["django_settings"] = \
                                    runtime.django_diffsettings(app_tmp_dir=app_tmp_dir)
                            dj_settings = runtime.collected_project_metadata.get("django_settings")
                            task_messages_layout.add_split(
                                Layout(name="dj-settings-header", ratio=1, size=None)
                            )
                            task_messages_layout["dj-settings-header"].update(
                                HeaderDjangoSettings()
                            )
                            for msg_index, settings_fld in enumerate(dj_settings.settings_with_titles()):
                                task_messages_layout.add_split(
                                    Layout(name=f"dj-settings-msg-{msg_index}", ratio=1, size=None)
                                )
                                task_messages_layout[f"dj-settings-msg-{msg_index}"].\
                                    update(
                                        Panel(
                                            f"{settings_fld[0]} - {settings_fld[1]}\n",
                                            border_style="green",
                                        )
                                    )
                        except DjangoDiffSettingsError:
                            if app_tmp_dir:
                                runtime.check_cleanup(app_tmp_dir)
                            # raise PythonRuntimeDjangoCheckError("django diffsettings command failed.")
                    elif job.id == install_dependencies_task:
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
                        job.id,
                        completed=1,
                        visible=True,
                        refresh=True,
                        description=description_done or job.fields.get("description_done"),
                        emoji_fld=job.fields.get("emoji_fld", "N/A"),
                        result_mark_fld=":heavy_check_mark:"
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
        app_name = randomname.get_name().lower()
        app_project = services.get(context, SandboxProject)
        try:
            wsgi_app = runtime.get_app(
                conf,
                db,
                app_name,
                service_id,
                app_project,
                pyvenv_dir,
                build_routers(app_name),
            )
            logger.info(wsgi_app.config_json)
            # console.print("[bold green]WSGI App has been provisioned.")
        except DjangoSettingsError:
            logger.error("[pikesquares] -- DjangoSettingsError --")
            raise typer.Exit() from None

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
from .commands import routers
from .commands import managed_services

app.add_typer(apps.app, name="apps")
app.add_typer(routers.app, name="routers")
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
    logger.info(f"About to execute command: {ctx.invoked_subcommand}")
    for key, value in os.environ.items():
        if key.startswith(("PIKESQUARES", "SCIE", "PEX", "PYTHON_VIRTUAL_ENV")):
            logger.info(f"{key}: {value}")

    is_root: bool = os.getuid() == 0
    logger.info(f"{os.getuid()=} {is_root=}")

    if ctx.invoked_subcommand in set({"bootstrap", "up"}) and not is_root:
        console.info("Please start server as root user. `sudo pikesquares up`")
        raise typer.Exit()

    pikesquares_version = version or os.environ.get("PIKESQUARES_VERSION")
    if not pikesquares_version:
        console.error("Unable to read the pikesquares version")
        raise typer.Exit(1)

    # console.info(f"PikeSquares: v{pikesquares_version}")
    context = services.init_context(ctx.ensure_object(dict))
    context = services.init_app(ctx.ensure_object(dict))
    context["cli-style"] = console.custom_style_dope

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
            logger.info(f"{varname=}")
            if cli_arg:
                logger.info(f"cli args: {cli_arg}.")
            if env_var_path_to_dir:
                logger.info(f"env var: {env_var_path_to_dir}")
            # ensure_sysdir(sysdir, varname)

            path_to_dir = cli_arg or env_var_path_to_dir or default_path_to_dir
            if isinstance(path_to_dir, str):
                path_to_dir = Path(path_to_dir)
            if not path_to_dir.exists():
                logger.info(f"creating dir: {path_to_dir}")
                make_system_dir(path_to_dir)
            override_settings[varname] = path_to_dir

    if version:
        override_settings["VERSION"] = version

    logger.info(f"{override_settings=}")

    try:
        register_app_conf(
            context,
            override_settings,
        )
    except AppConfigError as app_conf_error:
        logger.error(app_conf_error)
        raise typer.Abort() from None

    conf = services.get(context, AppConfig)
    db_path = conf.data_dir / "device-db.json"
    services.register_db(
        context,
        db_path,
    )
    db = services.get(context, TinyDB)
    logger.info(conf.model_dump())

    build_configs = True # ctx.invoked_subcommand == "bootstrap"
    register_device(
        context,
        Device,
        conf,
        db,
        build_config_on_init=build_configs,
    )
    device = services.get(context, Device)
    # device.ping()

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
    process_compose.register_process_compose(context, conf)
    # http_router = services.get(context, DefaultHttpRouter)
    # https_router = services.get(context, DefaultHttpsRouter)

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
