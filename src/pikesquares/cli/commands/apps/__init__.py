import shutil
import tempfile
import time
import traceback
from enum import Enum
from glob import glob
from pathlib import Path
from typing import Optional

import cuid
import questionary
import randomname
from aiopath import AsyncPath
import structlog
import typer
from cuid import cuid
from typing_extensions import Annotated

from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    Progress,
)

from pikesquares.services.apps.exceptions import (
    DjangoCheckError,
    DjangoDiffSettingsError,
    UvPipInstallError,
    UvPipListError,
    UvSyncError,
)
from pikesquares.cli.console import (
    HeaderDjangoChecks,
    HeaderDjangoSettings,
    make_layout,
    make_progress,
)
from pikesquares import services
from pikesquares.cli.cli import run_async
from pikesquares.conf import AppConfig
from pikesquares.domain.project import Project
from pikesquares.domain.router import HttpRouter
from pikesquares.domain.wsgi_app import WsgiApp
from pikesquares.services.data import Router, WsgiAppOptions

from ...console import console
from .utils import (
    create_venv,
    provision_base_dir,
    venv_pip_install,
)
from .validators import NameValidator

logger = structlog.get_logger()


class LanguageRuntime(str, Enum):
    python = "python"
    ruby = "ruby"
    php = "php"
    perl = "perl"


CHOSE_FILE_MYSELF = "-- Select the file myself --"

app = typer.Typer()


@app.command(short_help="Detect app runtime")
@app.command()
def detect(
    ctx: typer.Context,
):
    """
    Detect app runtime

    """
    context = ctx.ensure_object(dict)

    conf = services.get(context, AppConfig)
    custom_style = context.get("cli-style")
    logger.info("Detecting project")


@app.command(short_help="Create new app\nAliases: [i] create, new")
@app.command()
def create(
    ctx: typer.Context,
    project: Optional[str] = typer.Option("", "--in", "--in-project", help="Name or id of project to add new app"),
    name: Annotated[str, typer.Option("--name", "-n", help="app name")] = "",
    source: Annotated[str, typer.Option("--source", "-s", help="app source")] = "",
    # app_type: Annotated[str, typer.Option("--app-type", "-t", help="app source")] =  "",
    # router_address: Annotated[str, typer.Option("--router-address", "-r", help="ssl router address")] =  "",
    base_dir: Annotated[
        Path | None,
        typer.Option(
            "--base-dir",
            "-d",
            exists=True,
            # file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
            help="app base directory",
        ),
    ] = None,
    # runtime: Annotated[str, typer.Option("--runtime", "-r", help="app language runtime")] = "",
    runtime: Annotated[
        LanguageRuntime, typer.Option("--runtime", "-r", case_sensitive=False, help="app language runtime")
    ] = LanguageRuntime.python,
):
    """
    Create new app in project

    Aliases: [i] create, new
    """
    context = ctx.ensure_object(dict)

    db = services.get(context, TinyDB)
    conf = services.get(context, AppConfig)

    custom_style = context.get("cli-style")
    app_options = {}

    # APP Type
    # service_type = console.choose(
    #    "What type of app would you like to create?",
    #    choices=services.HandlerFactory.user_visible_apps(),
    # )
    service_type = "WSGI-App"
    # service ID
    service_type_prefix = service_type.replace("-", "_").lower()
    service_id = f"{service_type_prefix}_{cuid()}"

    base_dir = base_dir or provision_base_dir(custom_style)
    app_options["root_dir"] = base_dir
    app_name = (
        name
        or questionary.text(
            "Choose a name for your app: ",
            default=randomname.get_name().lower(),
            style=custom_style,
            validate=NameValidator,
        ).ask()
    )

    if not app_name:
        raise typer.Exit()


    # app_project = get_project(
    #    db,
    #    conf,
    #    project,
    #    services.get(context, SandboxProject),
    #    custom_style,
    # )
    #app_project = services.get(context, SandboxProject)
    app_options["project_id"] = app_project.service_id

    # Runtime
    runtime = questionary.select(
        "Select a language runtime for your app: ",
        choices=[
            "Python/WSGI",
            questionary.Separator(),
            questionary.Choice("ruby/Rack", disabled="coming soon"),
            questionary.Choice("PHP", disabled="coming soon"),
            questionary.Choice("perl/PSGI", disabled="coming soon"),
        ],
        style=custom_style,
    ).ask()
    if not runtime:
        raise typer.Exit()

    # WSGI File
    wsgi_file_q = questionary.path(
        "Enter the location of your app Python WSGI file:",
        default=str(base_dir),
        only_directories=False,
        style=custom_style,
    )
    wsgi_files_choices = [f for f in glob(f"{base_dir}/**/*wsgi*.py", recursive=True) if not "tests" in f]
    if len(wsgi_files_choices):
        wsgi_file = questionary.select(
            "Select a WSGI file: ",
            choices=wsgi_files_choices + [questionary.Separator(), CHOSE_FILE_MYSELF],
            style=custom_style,
        ).ask()
        if wsgi_file == CHOSE_FILE_MYSELF:
            wsgi_file = wsgi_file_q.ask()
    else:
        wsgi_file = wsgi_file_q.ask()

    app_options["wsgi_file"] = base_dir / wsgi_file

    # WSGI Module
    wsgi_module = questionary.text(
        "Enter your app Python WSGI module name: ",
        default="application",
        style=custom_style,
    ).ask()
    app_options["wsgi_module"] = wsgi_module

    # pip deps
    pip_req_file_q = questionary.path(
        "Enter your app pip requirements file: ",
        default=str(base_dir),
        only_directories=False,
        style=custom_style,
    )
    pip_req_files = glob(f"{base_dir}/**/requirements.txt", recursive=True)
    if len(pip_req_files):
        pip_req_file = questionary.select(
            "Select a pip requirements file: ",
            choices=pip_req_files + [questionary.Separator(), CHOSE_FILE_MYSELF],
            style=custom_style,
        ).ask()
        if pip_req_file == CHOSE_FILE_MYSELF:
            pip_req_file = pip_req_file_q.ask()
    else:
        pip_req_file = pip_req_file_q.ask()

    pip_req_file_path = base_dir / pip_req_file
    if pip_req_file_path.exists():
        # with console.status(f"creating a Python venv and installing dependencies", spinner="earth"):
        venv_dir = conf.data_dir / "venvs" / service_id
        create_venv(venv_dir)
        console.info("Created a Python virtualenv")
        if not venv_dir.exists():
            console.warning("unable to create python virtualenv")
            raise typer.Exit()
        app_options["pyvenv_dir"] = venv_dir
        app_reqs = list(filter(None, pip_req_file_path.read_text().split("\n")))
        console.info("Installing app dependencies")
        venv_pip_install(venv_dir, service_id, "--progress-bar", "off", *app_reqs, find_links=None)

    # Router
    # router = get_router(db, conf, app_name, custom_style)

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

    app_options["routers"] = routers

    console.info(app_options)
    app_options["workers"] = 3

    wsgi_app = WsgiApp(
        conf=services.get(context, AppConfig),
        db=db,
        service_id=service_id,
        name=app_name,
        app_options=WsgiAppOptions(**app_options),
        build_config_on_init=True,
    )
    with console.status(f"`{app_name}` is starting...", spinner="earth"):
        wsgi_app.up()
        for _ in range(10):
            if wsgi_app.get_service_status() == "running":
                for router in routers:
                    url = console.render_link(
                        f"{router.app_name}.pikesquares.dev",
                        port=str(router.subscription_server_port),
                        protocol=router.subscription_server_protocol,
                    )
                    console.success(f"🚀 App is available at {url}")
                raise typer.Exit()
            time.sleep(3)

        console.warning(f"could not start app [{app_name}]. giving up.")
        # wsgi_app.service_config.unlink()
        # console.info(f"removed app config {wsgi_app.name}")

    # [uWSGI http pid 3758459] rounded-hip.pikesquares.dev:8443 => marking 127.0.0.1:4018 as failed
    # [notify-socket] [subscription ack] rounded-hip.pikesquares.dev:8443 => new node: 127.0.0.1:4018

    # if selected_kit_name == "Custom":
    #    project_path = project_db.get(where('name') == project_id).get('path')
    #    opts = console.ask_for_options(
    #        service.default_options,
    #        defaults={'root_dir': project_path},
    #        label=lambda v: f"Enter {v.replace('_', ' ')}"
    #    )
    #    service_options.update(opts)
    # service.prepare_service_config(
    #    **service_options
    # )
    # console.success(f"Starting {service_type} service")
    # service.start()

    # service_data = {
    #    "cuid": service_id,
    #    "type": service_type,
    #    "path": str(Path(service.root_dir).resolve()),
    #    "parent_id": service.project_id,
    #    "options": service_options,
    #    "virtual_hosts": [vh.dict() for vh in service.virtual_hosts]
    # }

    # project_db = obj['project'](project_id)
    # apps = project_db.get(where('name') == project_id).get('apps')
    # apps.append(service_data)
    # project_db.update({'apps': apps}, where('name') == project_id)
    # console.success(f"{service_type} '{service_data.get('cuid')}' was successfully created in project '{project_id}'!")


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


@app.command(short_help="Show all apps in specific project.\nAliases:[i] apps, app list")
@run_async
async def ls(
    ctx: typer.Context,
    project: str = typer.Argument("", help="Project name"),
    show_id: bool = False,
):
    """
    Show all apps in specific project

    Aliases:[i] apps, app list
    """
    context = ctx.ensure_object(dict)
    # device_handler = obj.get("device-handler")
    custom_style = context.get("cli-style")

    conf = await services.aget(context, AppConfig)
    uow = await services.aget(context, UnitOfWork)
    device = context.get("device")
    if not device:
        console.error("unable to locate device in app context")
        raise typer.Exit(code=0) from None

    async with uow:
        attached_daemons = await uow.attached_daemons.list()
        for daemon in attached_daemons:
            try:
                daemon_stats_available  = bool(daemon.__class__.read_stats(daemon.stats_address))
            except StatsReadError:
                daemon_stats_available = False

            console.info(
                f"""{daemon.name} | \
{daemon.service_id} | \
{'Stats Up' if daemon_stats_available else 'Stats Down'} | \
{Path(daemon.pid_file).read_text()}
                """
            )



@app.command(short_help="Show all apps in specific project.\nAliases:[i] apps, app list")
@app.command()
def ls_deprecated(
    ctx: typer.Context,
    project: str = typer.Argument("", help="Project name"),
    show_id: bool = False,
):
    """
    Show all apps in specific project

    Aliases:[i] apps, app list
    """
    context = ctx.ensure_object(dict)
    # device_handler = obj.get("device-handler")
    custom_style = context.get("cli-style")


    db = services.get(context, TinyDB)
    # device_handler = services.get(obj, device.DeviceService)

    # if not project:
    #    available_projects = {
    #        p.get('name'): p.get('service_id') for p in projects_all(conf)
    #    }
    #    if not available_projects:
    #        console.warning(f"No projects were created, create at least one project first!")
    #        return
    #    project = console.choose(
    #        "Select project where you want to list apps",
    #        choices=available_projects
    #    )

    def get_project_id(project):
        return db.table('projects').get(Query().name == project)

    project_id = None
    if not project:
        projects_db = db.table('projects')
        project = questionary.select(
            "Select project: ",
            choices=[p.get("name") for p in projects_db.all()],
            style=custom_style,
        ).ask()
        project_id = get_project_id(project).get("service_id")
        assert project_id
    else:
        project_id = get_project_id(project)

    apps_out = []
    for app in db.table("apps").search(where("project_id") == project_id):
        service_id = app.get("service_id")
        # stats_socket = Path(conf.RUN_DIR) / f"{service_id}-stats.sock"
        # logger.debug(read_stats(str(stats_socket)))
        # logger.debug(f"{stats_socket=} {service_id=}")
        # status = get_service_status(
        #    (Path(conf.RUN_DIR) / f"{service_id}-stats.sock")
        # )
        apps_out.append(
            {
                "name": app.get("name"),
                # 'status': status or "uknown",
                "id": service_id,
            }
        )
    if not apps_out:
        console.info("You have not created any apps yet.")
        console.info("Create apps using the `pikesquares apps create` command")
    else:
        console.print_response(
            apps_out, title=f"Apps in project '{project}'", show_id=show_id, exclude=["parent_id", "options"]
        )


@app.command(short_help="Delete existing app by name or id\nAliases:[i] delete, rm")
@app.command()
def delete(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Option("--name", "-n", help="Name of app to delete")] = "",
):
    """
    Delete existing app by name or id

    Aliases:[i] delete, rm
    """
    obj = ctx.ensure_object(dict)
    custom_style = obj.get("cli-style")
@app.command(short_help="Rebuild configs for an existing app by name or id\nAliases:[i] rebuild-config, rc")
@app.command()
def rebuild_config(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Option("--name", "-n", help="Name of app to rebuild configs for")] = "",
):
    """
    Rebuild config for an existing app by name or id

    Aliases:[i] rebuild-config, rc
    """
    context = ctx.ensure_object(dict)
    # custom_style = obj.get("cli-style")

    db = services.get(context, TinyDB)
    conf = services.get(context, AppConfig)

    selected_app_cuid = "wsgi_app_cm395zdj60000rvj13a6vn6ro"

    apps_db = db.table("apps")
    app = apps_db.get(Query().service_id == selected_app_cuid)

    # "service_type": "WsgiAppService",
    # "name": "equilateral-refraction",
    # "service_id": "wsgi_app_cm3965vma000041j1g4a8wlfc",
    # "project_id": "project_sandbox",

    wsgi_app_handler = services.HandlerFactory.make_handler("WSGI-App")(
        WsgiApp(
            name=app.get("name"),
            service_id=selected_app_cuid,
            conf=conf,
            db=db,
        )
    )
    wsgi_app_handler.svc_model.parent_service_id = app.get("project_id")

    service_config = app["service_config"]["uwsgi"]

    app_options = {}
    app_options["root_dir"] = service_config[""]
    app_options["wsgi_file"] = service_config[""]
    app_options["wsgi_module"] = service_config[""]
    app_options["pyvenv_dir"] = service_config[""]
    app_options["router_id"] = service_config[""]
    app_options["workers"] = 3

    wsgi_app_handler.prepare_service_config(**app_options)
    wsgi_app_handler.connect()
    wsgi_app_handler.start()


if __name__ == "__main__":
    app()
