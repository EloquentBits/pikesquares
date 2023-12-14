from pathlib import Path
from typing import Optional
import shutil

import typer
from tinydb import where
import randomname

from cuid import cuid

from pikesquares import (
    get_service_status,
    https_router_up,
    get_first_available_port,
)
from ..console import console
from ..validators import ServiceNameValidator
from ..cli import app


ALIASES = ("rtrs", "rtr")
HELP = f"""
    Routers related commands.\n
    Aliases: [i]{', '.join(ALIASES)}[/i]
"""

proj_cmd = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    name="routers",
    help=HELP
)
for alias in ALIASES:
    app.add_typer(
        proj_cmd,
        name=alias,
        help=HELP,
        hidden=True
    )

@proj_cmd.command(short_help="Create a new router.\nAliases:[i] new")
@proj_cmd.command("new", hidden=True)
def create(
    ctx: typer.Context,
    #project_name: Optional[str] = typer.Argument("", help="New project name"),
):
    """
    Create a new router

    Aliases: [i] create, new
    """
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")
    port = 3017
    stats_server_port = 9897
    subscription_server_port = 5600

    #if not project_name:
    #    default_project_name = randomname.get_name()
    #    project_name = console.ask(
    #        f"Project name?",
    #        default=default_project_name,
    #        validators=[ServiceNameValidator]
    #    )

    https_router_up(
        client_config, 
        f"router_{cuid()}", 
        f"127.0.0.1:{get_first_available_port(port=port)}",
        f"127.0.0.1:{get_first_available_port(port=stats_server_port)}",
        f"127.0.0.1:{get_first_available_port(port=subscription_server_port)}",  
    )

#@proj_cmd.command(short_help="Start project.\nAliases:[i] run")
#@proj_cmd.command("run", hidden=True)
#def start(
#    ctx: typer.Context,
#    project_name: Optional[str] = typer.Argument("", help="Project to start"),
#):
#    """
#    Start project.

#    Aliases: [i] start, run
#    """
#    obj = ctx.ensure_object(dict)
#    client_config = obj.get("client_config")

#    device_db = obj['device']

    #for project_doc in db.table('projects'):
    #    project_up(client_config, project_doc.service_id)

#    if not project_name:
#        available_projects = {p.get('name'): p.get('cuid') for p in obj['projects']()}
#        if not available_projects:
#            console.warning("Create at least one project first, before starting it!")
#            return
#        project_name = console.choose("Select project you want to start", choices=available_projects)

#    project_ent = device_db.get(where('name') == project_name)

#    project_id = project_ent.get('cuid')
#    project_type = project_ent.get('type')
#    if project_type != "Project":
#        console.error(
#            "You've entered app name instead of project name!",
#            example=f"vc apps start '{project_name}'"
#        )
#        return

    #project = HandlerFactory.make_handler(project_type)(
    #    service_id=project_id,
    #    client_config=client_config,
    #)
    #if project.is_started():
    #    console.info(f"Project '{project_name}' is already started!")
    #    return

    #project.prepare_service_config()
    #project.connect()
    #project.start()
    #console.success(f"Project '{project_name}' was successfully started!")


#@proj_cmd.command(short_help="Stop project.\nAliases:[i] down")
#@proj_cmd.command("down", hidden=True)
#def stop(
#    ctx: typer.Context,
#    project_name: Optional[str] = typer.Argument("", help="Project to stop"),
#):
#    """
#    Stop project.

#    Aliases: [i] stop, down
#    """
#    obj = ctx.ensure_object(dict)
#    client_config = obj.get("client_config")

#    device_db = obj['device']

#    project_ent = device_db.search(where('name') == project_name)
#    if not project_ent:
#        console.error(f"Project with name '{project_name}' does not exists!")
#        return
#    else:
#        project_ent = project_ent[0]

#    project_id = project_ent.get('cuid')
#    project_type = project_ent.get('type')
#    if project_type != "Project":
#        console.error(
#            "You've entered app name instead of project name!",
#            example=f"vc apps stop '{project_name}'"
#        )
#        return

    #project = HandlerFactory.make_handler(project_type)(
    #    service_id=project_id,
    #    client_config=client_config,
    #)
    #if not project.is_started():
    #    console.info(f"Project '{project_name}' is not started!")
    #    return

    #project.connect()
    #project.stop()
    #console.success(f"Project '{project_name}' was successfully stopped!")


@app.command(
    "projects",
    rich_help_panel="Show",
    short_help="Show all projects in specific environment.\nAliases:[i] projects, projects list"
)
@app.command("proj", rich_help_panel="Show", hidden=True)
@proj_cmd.command("list")
def list_(
    ctx: typer.Context,
    show_id: bool = False
):
    """
    Show all projects on current device

    Aliases:[i] projects, projects list
    """

    obj = ctx.ensure_object(dict)
    client_config = obj.get('client_config')
    #device_db = obj['device']
    #show_fields = ['name', 'path', 'status', 'cuid']
    #for x in device_db:
    #    print(x)
    #projects = [
    #    {k: v for k, v in e.items() if k in show_fields}
    #    for e in device_db
    #]

    projects_table = obj['db'].table('projects')
    projects = []
    projects_count = len(projects_table.all())
    if not projects_count:
        console.warning("No projects were initialized, nothing to show!")
        return
    
    for project in projects_table.all():
        projects.append({
            'name': project.get('name'),
            'status': get_service_status(project.get('service_id'), client_config) or "Unknown",
            'id': project.get('service_id')
        })
    
    console.print_response(
        projects, title=f"Projects count: {projects_count}", show_id=show_id
    )


@proj_cmd.command("logs")
def logs(ctx: typer.Context, project_id: Optional[str] = typer.Argument("")):
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    if not project_id:
        available_projects = {p.get("name"): p.get("cuid") for p in obj['projects']()}
        project_name = console.choose("Choose project which you want to view logs:", choices=available_projects)
        project_id = available_projects.get(project_name)

    status = get_service_status(f"{project_id}-emperor", client_config)

    project_log_file = Path(f"{client_config.LOG_DIR}/{project_id}.log")
    if project_log_file.exists() and project_log_file.is_file():
        console.pager(
            project_log_file.read_text(),
            status_bar_format=f"{project_log_file.resolve()} (status: {status})"
        )
    else:
        console.error(
            f"Error:\nLog file {project_log_file} not exists!",
            hint=f"Check the device log file for possible errors"
        )


@proj_cmd.command(short_help="Delete existing project by name or id\nAliases:[i] delete, rm")
@proj_cmd.command("rm", hidden=True)
def delete(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Argument("", help="Name of project to remove"),
):
    """
    Delete existing project by name or id

    Aliases:[i] delete, rm
    """
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    device_db = obj['device']

    projects_choices = {
        k.get('name'): (k.get('cuid'), k.get('path'))
        for k in device_db.search(where("type") == 'Project')
    }
    if not projects_choices:
        console.warning("No projects were initialized, nothing to delete!")
        return
    
    selected_project_name = project_name
    if not selected_project_name:
        selected_project_name = console.choose(
            "Which project you want to delete?",
            choices=projects_choices,
        )

    # rm project sources
    selected_project_cuid, selected_project_path = projects_choices.get(selected_project_name)
    if Path(selected_project_path).exists() and console.confirm(f"Are you sure you want to delete: {selected_project_path}"):
        shutil.rmtree(selected_project_path)

    # rm project configs
    selected_project_config_path = Path(client_config.CONFIG_DIR) / selected_project_cuid
    selected_project_config_path.with_suffix('.json').unlink(missing_ok=True)
    if Path(selected_project_config_path).exists():
        shutil.rmtree(str(selected_project_config_path.resolve()))

    # rm project runtimes
    for file in Path(client_config.RUN_DIR).iterdir():
        if selected_project_cuid in str(file.resolve()):
            file.unlink(missing_ok=True)

    # rm project from db
    device_db.remove(where('cuid') == selected_project_cuid)

    console.success(f"Removed project '{selected_project_name}'!")


app.add_typer(proj_cmd)
