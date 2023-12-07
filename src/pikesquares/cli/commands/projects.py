from pathlib import Path
from typing import Optional
import shutil

import typer
from tinydb import where
import randomname

from cuid import cuid

from pikesquares import (
    HandlerFactory, 
    get_service_status,
)

from ..console import console
from ..validators import ServiceNameValidator
from ..cli import app


ALIASES = ("projs", "prj")
HELP = f"""
    Projects related commands.\n
    Aliases: [i]{', '.join(ALIASES)}[/i]
"""

proj_cmd = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    name="projects",
    help=HELP
)
for alias in ALIASES:
    app.add_typer(
        proj_cmd,
        name=alias,
        help=HELP,
        hidden=True
    )

@proj_cmd.command(short_help="Create new project.\nAliases:[i] new")
@proj_cmd.command("new", hidden=True)
def create(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Argument("", help="New project name"),
):
    """
    Create new project in environment

    Aliases: [i] create, new
    """
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    if not project_name:
        default_project_name = randomname.get_name()
        project_name = console.ask(
            f"Project name?",
            default=default_project_name,
            validators=[ServiceNameValidator]
        )

    project_id = f"project_{cuid()}"

    console.info("Preparing project environment")
    project_dir = Path(client_config.DATA_DIR) / "projects" / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    console.info(f"Creating project dir: {project_dir.resolve()}")

    device_db = obj['device']
    device_db.insert({
        'name': project_name,
        'cuid': project_id,
        'type': "Project",
        'path': str(project_dir.resolve())
    })

    proj_db = obj['project'](project_name)

    project = HandlerFactory.make_handler("Project")(
        service_id=project_id,
        client_config=client_config,
    )
    proj_data = {
        "cuid": project_id,
        "name": project_name,
        "path": str(project_dir.resolve()),
        "apps": []
    }

    project = HandlerFactory.make_handler("Project")(
        service_id=project_id,
        client_config=client_config,
    )
    project.prepare_service_config()
    proj_db.insert(proj_data)

    project.connect()
    project.start()
    console.success(f"Project '{project_name}' was successfully created!")

@proj_cmd.command(short_help="Start project.\nAliases:[i] run")
@proj_cmd.command("run", hidden=True)
def start(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Argument("", help="Project to start"),
):
    """
    Start project.

    Aliases: [i] start, run
    """
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    device_db = obj['device']

    if not project_name:
        available_projects = {p.get('name'): p.get('cuid') for p in obj['projects']()}
        project_name = console.choose("Select project you want to start", choices=available_projects)

    project_ent = device_db.get(where('name') == project_name)

    project_id = project_ent.get('cuid')
    project_type = project_ent.get('type')
    if project_type != "Project":
        console.error(
            "You've entered app name instead of project name!",
            example=f"vc apps start '{project_name}'"
        )
        return

    project = HandlerFactory.make_handler(project_type)(
        service_id=project_id,
        client_config=client_config,
    )
    if project.is_started():
        console.info(f"Project '{project_name}' is already started!")
        return

    project.prepare_service_config()
    project.connect()
    project.start()
    console.success(f"Project '{project_name}' was successfully started!")


@proj_cmd.command(short_help="Stop project.\nAliases:[i] down")
@proj_cmd.command("down", hidden=True)
def stop(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Argument("", help="Project to stop"),
):
    """
    Stop project.

    Aliases: [i] stop, down
    """
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    device_db = obj['device']

    project_ent = device_db.search(where('name') == project_name)
    if not project_ent:
        console.error(f"Project with name '{project_name}' does not exists!")
        return
    else:
        project_ent = project_ent[0]

    project_id = project_ent.get('cuid')
    project_type = project_ent.get('type')
    if project_type != "Project":
        console.error(
            "You've entered app name instead of project name!",
            example=f"vc apps stop '{project_name}'"
        )
        return

    project = HandlerFactory.make_handler(project_type)(
        service_id=project_id,
        client_config=client_config,
    )
    if not project.is_started():
        console.info(f"Project '{project_name}' is not started!")
        return

    project.connect()
    project.stop()
    console.success(f"Project '{project_name}' was successfully stopped!")


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
    device_db = obj['device']

    show_fields = ['name', 'path', 'status', 'cuid']
    projects = [
        {k: v for k, v in e.items() if k in show_fields}
        for e in device_db
    ]
    if not projects:
        console.warning("No projects were initialized, nothing to show!")
        return
    
    for p in projects:
        p.update({'status': get_service_status(p.get('cuid'), client_config)})
    
    console.print_response(projects, title=f"Projects count: {len(projects)}", show_id=show_id)


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
