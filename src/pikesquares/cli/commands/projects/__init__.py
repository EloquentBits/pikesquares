from pathlib import Path
from typing import Optional

import randomname
import structlog

# import shutil
import typer
from cuid import cuid

# from pikesquares import (
#    get_service_status,
# )
from pikesquares import services
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.conf import AppConfig
from pikesquares.cli.cli import run_async
from pikesquares.cli.console import console
from pikesquares.cli.validators import ServiceNameValidator

logger = structlog.get_logger()


# ALIASES = ("proj", "prj")
# HELP = f"""
#    Projects related commands.\n
#    Aliases: [i]{', '.join(ALIASES)}[/i]
# """

# proj_cmd = typer.Typer(no_args_is_help=True, rich_markup_mode="rich", name="projects", help=HELP)
# for alias in ALIASES:
#    app.add_typer(proj_cmd, name=alias, help=HELP, hidden=True)

app = typer.Typer()


@app.command(short_help="Create new project.\nAliases:[i] new")
@app.command(
    # "new", hidden=True
)
def create(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Argument("", help="New project name"),
):
    """
    Create new project in environment

    Aliases: [i] create, new
    """
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    if not project_name:
        default_project_name = randomname.get_name()
        project_name = console.ask(f"Project name?", default=default_project_name, validators=[ServiceNameValidator])

    # console.success(f"Project '{project_name}' was successfully created!")
    project_up(conf, project_name, f"project_{cuid()}")


@app.command("up")
def up(ctx: typer.Context, name: Optional[str] = typer.Argument("")):
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")
    projects = projects_all(conf)
    for project in projects:
        name = project.get('name')
        status = (get_service_status(project.get('service_id'), conf) or "Unknown",)
        service_id = project.get('service_id')
        print(f"{status=} {name} [{service_id}]")
        project_up(conf, name, service_id)


@app.command(
    "projects",
    rich_help_panel="Show",
    short_help="Show all projects in specific environment.\nAliases:[i] projects, projects list",
)
# @app.command("proj", rich_help_panel="Show", hidden=True)
@app.command("list")
@run_async
async def list_(ctx: typer.Context, show_id: bool = False):
    """
    Show all projects on current device

    Aliases:[i] projects, projects list
    """
    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)
    uow = await services.aget(context, UnitOfWork)
    device = context.get("device")

    projects = await uow.projects.list()
    if not len(projects):
        console.warning("No projects were initialized, nothing to show!")
        raise typer.Exit()

    projects_out = []
    for project in projects:
        projects_out.append(
            {
                'name': project.name,
                'status': "status",  # get_service_status(project.get('service_id'), conf) or "Unknown",
                'id': project.service_id,
            }
        )
    console.print_response(projects_out, title=f"Projects count: {len(projects)}", show_id=show_id)


@app.command("logs")
def logs(ctx: typer.Context, project_id: Optional[str] = typer.Argument("")):
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    if not project_id:
        available_projects = {p.get("name"): p.get("cuid") for p in obj['projects']()}
        project_name = console.choose("Choose project which you want to view logs:", choices=available_projects)
        project_id = available_projects.get(project_name)

    status = get_service_status(f"{project_id}-emperor", conf)

    project_log_file = Path(f"{conf.log_dir}/{project_id}.log")
    if project_log_file.exists() and project_log_file.is_file():
        console.pager(
            project_log_file.read_text(), status_bar_format=f"{project_log_file.resolve()} (status: {status})"
        )
    else:
        console.error(
            f"Error:\nLog file {project_log_file} not exists!", hint=f"Check the device log file for possible errors"
        )


@app.command(short_help="Delete existing project by name or id\nAliases:[i] delete, rm")
@app.command("rm", hidden=True)
def delete(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Argument("", help="Name of project to remove"),
):
    """
    Delete existing project by name or id

    Aliases:[i] delete, rm
    """
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    # device_db = obj['device']

    # projects_choices = {
    #    k.get('name'): (k.get('cuid'), k.get('path'))
    #    for k in device_db.search(where("type") == 'Project')
    # }
    # if not projects_choices:
    #    console.warning("No projects were initialized, nothing to delete!")
    #    return

    # selected_project_name = project_name
    # if not selected_project_name:
    #    selected_project_name = console.choose(
    #        "Which project you want to delete?",
    #        choices=projects_choices,
    #    )

    # rm project sources
    # selected_project_cuid, selected_project_path = projects_choices.get(selected_project_name)
    # if Path(selected_project_path).exists() and console.confirm(f"Are you sure you want to delete: {selected_project_path}"):
    #    shutil.rmtree(selected_project_path)

    # rm project configs
    # selected_project_config_path = Path(conf.CONFIG_DIR) / selected_project_cuid
    # selected_project_config_path.with_suffix('.json').unlink(missing_ok=True)
    # if Path(selected_project_config_path).exists():
    #    shutil.rmtree(str(selected_project_config_path.resolve()))

    # rm project runtimes
    # for file in Path(conf.RUN_DIR).iterdir():
    #    if selected_project_cuid in str(file.resolve()):
    #        file.unlink(missing_ok=True)

    # rm project from db
    # device_db.remove(where('cuid') == selected_project_cuid)

    # console.success(f"Removed project '{selected_project_name}'!")


# @app.command(short_help="Start project.\nAliases:[i] run")
# @app.command("run", hidden=True)
# def start(
#    ctx: typer.Context,
#    project_name: Optional[str] = typer.Argument("", help="Project to start"),
# ):
#    """
#    Start project.

#    Aliases: [i] start, run
#    """
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    device_db = obj['device']

# for project_doc in db.table('projects'):
#    project_up(conf, project_doc.service_id)

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

# project = HandlerFactory.make_handler(project_type)(
#    service_id=project_id,
#    conf=conf,
# )
# if project.is_started():
#    console.info(f"Project '{project_name}' is already started!")
#    return

# project.prepare_service_config()
# project.connect()
# project.start()
# console.success(f"Project '{project_name}' was successfully started!")


# @app.command(short_help="Stop project.\nAliases:[i] down")
# @app.command("down", hidden=True)
# def stop(
#    ctx: typer.Context,
#    project_name: Optional[str] = typer.Argument("", help="Project to stop"),
# ):
#    """
#    Stop project.

#    Aliases: [i] stop, down
#    """
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

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

# project = HandlerFactory.make_handler(project_type)(
#    service_id=project_id,
#    conf=conf,
# )
# if not project.is_started():
#    console.info(f"Project '{project_name}' is not started!")
#    return

# project.connect()
# project.stop()
# console.success(f"Project '{project_name}' was successfully stopped!")

# app.add_typer(app)

if __name__ == "__main__":
    app()
