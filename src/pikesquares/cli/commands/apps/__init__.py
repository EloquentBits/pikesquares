import time
from pathlib import Path
from enum import Enum
from typing_extensions import Annotated
from typing import Optional
from glob import glob

import typer
import questionary
import randomname
from cuid import cuid
from tinydb import TinyDB, where, Query
import structlog

from .validators import NameValidator

from pikesquares.conf import AppConfig
from pikesquares import services
from pikesquares.services.project import SandboxProject, Project
from pikesquares.services.app import WsgiApp
from pikesquares.services.router import (
    DefaultHttpsRouter,
    DefaultHttpRouter,
)
from pikesquares.services.data import WsgiAppOptions, Router
from ...console import console

from .utils import (
    provision_base_dir,
    create_venv,
    venv_pip_install,
)

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

    db = services.get(context, TinyDB)
    conf = services.get(context, AppConfig)

    custom_style = context.get("cli-style")

    logger.info("Detecting project")


@app.command(short_help="Create new app\nAliases: [i] create, new")
@app.command()
def create(
    ctx: typer.Context,
    project: Optional[str] = typer.Option("", "--in", "--in-project",
        help="Name or id of project to add new app"
    ),
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
        )
    ] = None,

    # runtime: Annotated[str, typer.Option("--runtime", "-r", help="app language runtime")] = "",
    runtime: Annotated[
        LanguageRuntime,
        typer.Option("--runtime", "-r", case_sensitive=False, help="app language runtime")
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
    app_name = name or questionary.text(
        "Choose a name for your app: ",
        default=randomname.get_name().lower(),
        style=custom_style,
        validate=NameValidator,
    ).ask()

    if not app_name:
        raise typer.Exit()

    # app_project = get_project(
    #    db,
    #    conf,
    #    project,
    #    services.get(context, SandboxProject),
    #    custom_style,
    # )
    app_project = services.get(context, SandboxProject)
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

    #if selected_kit_name == "Custom":
    #    project_path = project_db.get(where('name') == project_id).get('path')
    #    opts = console.ask_for_options(
    #        service.default_options,
    #        defaults={'root_dir': project_path},
    #        label=lambda v: f"Enter {v.replace('_', ' ')}"
    #    )
    #    service_options.update(opts)
    #service.prepare_service_config(
    #    **service_options
    #)
    #console.success(f"Starting {service_type} service")
    #service.start()

    #service_data = {
    #    "cuid": service_id,
    #    "type": service_type,
    #    "path": str(Path(service.root_dir).resolve()),
    #    "parent_id": service.project_id,
    #    "options": service_options,
    #    "virtual_hosts": [vh.dict() for vh in service.virtual_hosts]
    #}

    #project_db = obj['project'](project_id)
    #apps = project_db.get(where('name') == project_id).get('apps')
    #apps.append(service_data)
    #project_db.update({'apps': apps}, where('name') == project_id)
    #console.success(f"{service_type} '{service_data.get('cuid')}' was successfully created in project '{project_id}'!")


@app.command(
    short_help="Show all apps in specific project.\nAliases:[i] apps, app list"
)
@app.command()
def ls(
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
        apps_out.append({
            "name": app.get("name"),
            # 'status': status or "uknown",
            "id": service_id,
        })
    if not apps_out:
        console.info("You have not created any apps yet.")
        console.info("Create apps using the `pikesquares apps create` command")
    else:
        console.print_response(
            apps_out,
            title=f"Apps in project '{project}'",
            show_id=show_id,
            exclude=["parent_id", "options"]
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

    db = services.get(obj, TinyDB)
    device = services.get(obj, services.Device)

    selected_app_cuid = None
    if not app_name:
        apps_db = db.table("apps")
        apps_all = apps_db.all()
        if not len(apps_all):
            console.info("no apps available.")
            raise typer.Exit()

        apps_choices = []
        for app in apps_all:
            apps_choices.append(
                questionary.Choice(
                    f"{app.get('name')} [{app.get('service_id')}",
                    value=app.get("service_id"),
                )
            )
        prompt_apps_to_delete = questionary.checkbox(
            "Select the app(s) to be deleted?",
            choices=apps_choices,
            style=custom_style,
        )
        for selected_app_cuid in prompt_apps_to_delete.ask() or []:
            console.info(f"selected app to delete: {selected_app_cuid=}")

            # rm app configs
            app = apps_db.get(Query().service_id == selected_app_cuid)
            project_id = app.get("project_id")
            selected_app_config_path = device.config_dir / \
                f"{project_id}" / "apps" \
                / f"{selected_app_cuid}.json"

            if selected_app_config_path.exists():
                selected_app_config_path.unlink(missing_ok=True)
                console.info(f"deleted app config @ {selected_app_cuid}")
            else:
                console.info(f"{str(selected_app_config_path)} does not exist")

            apps_db.remove(where("service_id") == selected_app_cuid)
            console.success(f"Removed app [{selected_app_cuid}]")


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
        services.WsgiApp(
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
