from pathlib import Path
import shutil
from typing import Optional

from tinydb import where
import typer
import questionary
import randomname
from cuid import cuid

from pikesquares import (
    HandlerFactory, 
    get_service_status,
    wsgi_app_up,
    projects_all,
)
from ..console import console
from ..cli import app
from ..validators import ServiceNameValidator

# def django_app_prepare(app_dir, wsgi_file, app_venv):
    # vc.wsgi:application
    # vc - source module
    # pico_django:application
    # in root folder always (not always)
    # manage.py
    # requirements.txt

ALIASES = ("applications", "app")
HELP = f"""
    Application commands.\n
    Aliases: [i]{', '.join(ALIASES)}[/i]
"""

apps_cmd = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    name="apps",
    help=HELP
)
for alias in ALIASES:
    app.add_typer(
        apps_cmd,
        name=alias,
        help=HELP,
        hidden=True
    )

@apps_cmd.command(short_help="Create new app in project\nAliases: [i] create, new")
@apps_cmd.command("new", hidden=True)
def create(
    ctx: typer.Context,
    project_name: str = typer.Option("", "--in", "--in-project", help="Name or id of project to add new app"),
):
    """
    Create new app in project

    Aliases: [i] create, new
    """
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    available_projects = {
        p.get('name'): p.get('service_id') for p in projects_all(client_config)
    }
    if not available_projects:
        console.warning(f"No projects were created, create at least one project first!")
        return

    if not project_name:
        project_name = console.choose(
            "Select project where you want to create app", 
            choices=available_projects
        )

    service_type = questionary.select(
        "What type of service would you like to create?",
        choices=HandlerFactory.user_visible_services(),
    ).ask()
    
    service_name = console.ask(
        "Enter your service name: ", 
        default=randomname.get_name(), 
        validators=[ServiceNameValidator]
    )
    service_type_prefix = service_type.replace('-', '_').lower()
    service_id = f"{service_type_prefix}_{cuid()}"
    #service = HandlerFactory.make_handler(service_type)(
    #    service_id=service_id,
    #    client_config=client_config,
    #)
    app_options = dict()
    app_options["root_dir"] = "/home/pk/dev/vconf-test-wsgiapp/simple-wsgi-app"
    app_options["pyvenv_dir"] = "/home/pk/dev/vconf-test-wsgiapp/simple-wsgi-app/venv"
    app_options["wsgi_file"] = "/home/pk/dev/vconf-test-wsgiapp/simple-wsgi-app/src/simple_wsgi_app/simple_app.py"
    app_options["wsgi_module"] = "application"

    wsgi_app_up(
        client_config,
        service_name,
        available_projects.get(project_name),
        service_id,
        **app_options,
    )

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
    "apps",
    rich_help_panel="Show",
    short_help="Show all apps in specific project.\nAliases:[i] apps, app list"
)
@app.command("proj", rich_help_panel="Show", hidden=True)
@apps_cmd.command("list")
def list_(
    ctx: typer.Context,
    project: str = typer.Argument("", help="Project name or id"),
    show_id: bool = False
):
    """
    Show all apps in specific project

    Aliases:[i] apps, app list
    """
    
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    if not project:
        available_projects = {p.get('name'): p.get('cuid') for p in obj['projects']()}
        if not available_projects:
            console.warning(f"No projects were created, create at least one project first!")
            return
        project = console.choose("Select project where you want to list apps", choices=available_projects)
    
    project_db = obj['project'](project)
    if not project_db:
        console.warning(f"Project '{project}' not exists!")
        return
    apps = project_db.get(where('name') == project).get('apps')
    for a in apps:
        a.update({'status': get_service_status(a.get('cuid'), client_config)})

    console.print_response(apps, title=f"Apps in project '{project}'", show_id=show_id, exclude=['parent_id', 'options'])


@apps_cmd.command("logs", short_help="Show app logs")
def logs(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(""),
    app_id: Optional[str] = typer.Argument("")
):

    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    if not project_id:
        available_projects = {p.get("name"): p.get("cuid") for p in obj['projects']()}
        if not available_projects:
            console.warning(f"No projects were created, create at least one project first!")
            return
        project_name = console.choose("Choose project which you want to view logs:", choices=available_projects)
        project_id = available_projects.get(project_name)
    
    project_db = obj['project'](project_name)

    if not app_id:
        apps = {
            a.get("name"): a.get("cuid")
            for a in project_db.get(where('name') == project_name).get('apps')
        }
        app_name = console.choose("Choose app you want to view logs:", choices=apps)
        app_id = apps.get(app_name)

    status = get_service_status(f"{app_id}", client_config)

    project_log_file = Path(f"{client_config.LOG_DIR}/{project_id}.log")
    app_log_file = Path(f"{client_config.LOG_DIR}/{app_id}.log")
    if app_log_file.exists() and app_log_file.is_file():
        console.pager(
            app_log_file.read_text(),
            status_bar_format=f"{app_log_file.resolve()} (status: {status})"
        )
    else:
        console.error(
            f"Error:\nLog file {app_log_file} not exists!",
            hint=f"Check the project log file {project_log_file} for possible errors"
        )

@apps_cmd.command("logs")
def logs(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(""),
    app_id: Optional[str] = typer.Argument("")
):
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    if not project_id:
        available_projects = {p.get("name"): p.get("cuid") for p in obj['projects']()}
        project_name = console.choose("Choose project which you want to view logs:", choices=available_projects)
        project_id = available_projects.get(project_name)
    
    project_db = obj['project'](project_name)

    if not app_id:
        apps = {
            a.get("name"): a.get("cuid")
            for a in project_db.get(where('name') == project_name).get('apps')
        }
        app_name = console.choose("Choose app you want to view logs:", choices=apps)
        app_id = apps.get(app_name)

    status = get_service_status(f"{app_id}", client_config)

    project_log_file = Path(f"{client_config.LOG_DIR}/{project_id}.log")
    app_log_file = Path(f"{client_config.LOG_DIR}/{app_id}.log")
    if app_log_file.exists() and app_log_file.is_file():
        console.pager(
            app_log_file.read_text(),
            status_bar_format=f"{app_log_file.resolve()} (status: {status})"
        )
    else:
        console.error(
            f"Error:\nLog file {app_log_file} not exists!",
            hint=f"Check the project log file {project_log_file} for possible errors"
        )

@apps_cmd.command(short_help="Start app.\nAliases:[i] run")
@apps_cmd.command("run", hidden=True)
def start(
    ctx: typer.Context,
    app_name: Optional[str] = typer.Argument("", help="App to start"),
    project_id: str = typer.Option("", "--in", "--in-project", help="Name or id of project to start app"),
):
    """
    Start new app in project

    Aliases: [i] create, new
    """
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    if not project_id:
        available_projects = {p.get('name'): p.get('cuid') for p in obj['projects']()}
        if not available_projects:
            console.warning(f"No projects were created, create at least one project first!")
            return
        project_name = console.choose("Select project where you want to start app", choices=available_projects)
        project_id = available_projects.get(project_name)

    project_db = obj['project'](project_name)
    
    apps = {a.get('name'): a for a in project_db.get(where('name') == project_name).get('apps')}
    if not apps:
        console.warning(f"No apps were created in this project, create at least one app first!")
        return

    if not app_name:
        app_name = console.choose("Select app you want to start in this project", choices=apps)

    app_ent = apps.get(app_name)
    if not app_ent:
        console.error(f"Application with name '{app_name}' does not exists!")
        return

    app_id = app_ent.get('cuid')
    app_type = app_ent.get('type')
    app_root_dir = app_ent.get('path')
    app_opts = app_ent.get('options', {})
    if app_type == "Project":
        console.error(
            "You've entered project name instead of app name!",
            example=f"vc projects start '{app_name}'"
        )
        return

    app = HandlerFactory.make_handler(app_type)(
        service_id=app_id,
        client_config=client_config,
    )
    console.info(f"Configuring {app_type} service")
    service_opts = dict(
        project_id=project_id,
        root_dir=app_root_dir,
    )
    service_opts.update(app_opts)
    app.prepare_service_config(**service_opts)
    console.info(f"Connecting {app_type} service")
    app.connect()

    if not app.is_started():
        console.info(f"Starting {app_type} service")
        app.start()
        console.success(f"{app_type} '{app_name}' was successfully started in project '{project_id}'!")
    
    lines = []
    for vh in app.virtual_hosts:
        _, port = vh.address.split(':')
        lines.append(f"\t{console.render_link(address=vh.address, port=port, protocol=vh.protocol)}")
        lines.extend([f"\t{console.render_link(address=n, port=port, protocol=vh.protocol)}" for n in vh.server_names])
    res = "\n".join(lines)
    console.info(f"{app_type} '{app_name}' is available on:\n{res}")


@apps_cmd.command(short_help="Stop app.\nAliases:[i] down")
@apps_cmd.command("down", hidden=True)
def stop(
    ctx: typer.Context,
    app_name: Optional[str] = typer.Argument("", help="App to stop"),
    project_id: str = typer.Option("", "--in", "--in-project", help="Name or id of project to stop app"),
):
    """
    Stop new app in project

    Aliases: [i] create, new
    """
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    if not project_id:
        available_projects = {p.get('name'): p.get('cuid') for p in obj['projects']()}
        if not available_projects:
            console.warning(f"No projects were created, create at least one project first!")
            return
        project_name = console.choose("Select project where you want to stop app", choices=available_projects)
        project_id = available_projects.get(project_name)

    project_db = obj['project'](project_name)
    
    apps = {a.get('name'): a for a in project_db.get(where('name') == project_name).get('apps')}
    if not apps:
        console.warning(f"No apps were created in this project, create at least one app first!")
        return

    if not app_name:
        app_name = console.choose("Select app you want to stop in this project", choices=apps)

    app_ent = apps.get(app_name)
    if not app_ent:
        console.error(f"Application with name '{app_name}' does not exists!")
        return

    app_id = app_ent.get('cuid')
    app_type = app_ent.get('type')
    if app_type == "Project":
        console.error(
            "You've entered project name instead of app name!",
            example=f"vc projects stop '{app_name}'"
        )
        return

    app = HandlerFactory.make_handler(app_type)(
        service_id=app_id,
        parent_service_id=project_id,
        client_config=client_config,
    )
    app.connect()
    if app.is_started():
        app.stop()
        console.success(f"{app_type} '{app_name}' was successfully stopped in project '{project_id}'!")
    else:
        console.info(f"{app_type} '{app_name}' is already stopped!")


@apps_cmd.command(short_help="Delete existing app by name or id\nAliases:[i] delete, rm")
@apps_cmd.command("rm", hidden=True)
def delete(
    ctx: typer.Context,
    app_name: str = typer.Argument("", help="Name of app to delete"),
    proj_name: Optional[str] = typer.Option("", "--from", help="Name of project to delete app"),
):
    """
    Delete existing app by name or id

    Aliases:[i] delete, rm
    """
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    if not proj_name:
        available_projects = {p.get("name"): p.get("cuid") for p in obj['projects']()}
        if not available_projects:
            console.warning(f"No projects were created, create at least one project first!")
            return
        proj_name = console.choose("Choose project where you want to delete app:", choices=available_projects)

    project_db = obj['project'](proj_name)

    apps_choices = {
        k.get('name'): k.get('cuid')
        for k in project_db.get(where('name') == proj_name).get('apps')
    }
    if not apps_choices:
        console.warning(f"No apps were initialized in project '{proj_name}', nothing to delete!")
        return

    print(apps_choices)
    
    if not app_name:
        app_name = console.choose(
            f"Which app you want to delete from project '{proj_name}'?",
            choices=apps_choices,
        )

    selected_app_cuid = apps_choices.get(app_name)

    # rm app configs
    selected_app_config_path = Path(client_config.CONFIG_DIR) / selected_app_cuid
    selected_app_config_path.with_suffix('.json').unlink(missing_ok=True)
    if Path(selected_app_config_path).exists():
        shutil.rmtree(str(selected_app_config_path.resolve()))

    # rm app runtimes
    for file in Path(client_config.RUN_DIR).iterdir():
        if selected_app_cuid in str(file.resolve()):
            file.unlink(missing_ok=True)

    # rm project from db
    project_db.update({'apps': [
        a
        for a in project_db.get(where('name') == proj_name).get('apps')
        if a.get('cuid') != selected_app_cuid
    ]})

    console.success(f"Removed app '{app_name}' from project '{proj_name}'!")


app.add_typer(apps_cmd)
