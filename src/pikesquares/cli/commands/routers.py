from pathlib import Path
#from typing import Optional
#import shutil

import typer
from typing_extensions import Annotated
from tinydb import TinyDB, where, Query

from cuid import cuid
import questionary

from pikesquares import (
    get_service_status,
    get_first_available_port,
)
from pikesquares.services.router import (
    https_router_up,
    https_routers_all,
)
from ..console import console
#from ..validators import ServiceNameValidator
from ..cli import app


ALIASES = ("rtrs", "rtr")
HELP = f"""
    Routers related commands.\n
    Aliases: [i]{', '.join(ALIASES)}[/i]
"""

routers_cmd = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="rich",
    name="routers",
    help=HELP
)
for alias in ALIASES:
    app.add_typer(
        routers_cmd,
        name=alias,
        help=HELP,
        hidden=True
    )

@routers_cmd.command(short_help="Create a new router.\nAliases:[i] new")
@routers_cmd.command("new", hidden=True)
def create(
    ctx: typer.Context,
    #project_name: Optional[str] = typer.Argument("", help="New project name"),
):
    """
    Create a new router

    Aliases: [i] create, new
    """
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")
    # if not project_name:
    #    default_project_name = randomname.get_name()
    #    project_name = console.ask(
    #        f"Project name?",
    #        default=default_project_name,
    #        validators=[ServiceNameValidator]
    #    )

    port = questionary.text(
        f"Enter the port for the Https Router: ",
        default=str(get_first_available_port(port=8443)),
        style=console.custom_style_dope,
    ).ask()
    https_router_up(
        conf,
        f"router_{cuid()}",
        f"0.0.0.0:{port}",
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
#    conf = obj.get("conf")

#    device_db = obj['device']

    #for project_doc in db.table('projects'):
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

    #project = HandlerFactory.make_handler(project_type)(
    #    service_id=project_id,
    #    conf=conf,
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

    #project = HandlerFactory.make_handler(project_type)(
    #    service_id=project_id,
    #    conf=conf,
    #)
    #if not project.is_started():
    #    console.info(f"Project '{project_name}' is not started!")
    #    return

    #project.connect()
    #project.stop()
    #console.success(f"Project '{project_name}' was successfully stopped!")


@app.command(
    "routers",
    rich_help_panel="Show",
    short_help="Show all routers.\nAliases:[i] routers, routers list"
)
@app.command("routers", rich_help_panel="Show", hidden=True)
@routers_cmd.command("list")
def list_(
    ctx: typer.Context,
    show_id: bool = False
):
    """
    Show all projects on current device

    Aliases:[i] projects, projects list
    """

    obj = ctx.ensure_object(dict)
    conf = obj.get('conf')
    routers = https_routers_all(conf)
    if not len(routers):
        console.warning("No routers were created, nothing to show!")
        raise typer.Exit()
    
    routers_out = []
    for router in routers:
        routers_out.append({
            'name': router.get('name'),
            'status': get_service_status(
                Path(conf.RUN_DIR) / router.get('service_id') + "-stats.sock",
            ) or "Unknown",
            'id': router.get('service_id')
        })
    console.print_response(
        routers_out, title=f"Routers count: {len(routers)}", show_id=show_id
    )

#@routers_cmd.command("logs")
#def logs(ctx: typer.Context, project_id: Optional[str] = typer.Argument("")):
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    if not project_id:
#        available_projects = {p.get("name"): p.get("cuid") for p in obj['projects']()}
#        project_name = console.choose("Choose project which you want to view logs:", choices=available_projects)
#        project_id = available_projects.get(project_name)
#
#    status = get_service_status(f"{project_id}-emperor", conf)
#
#    project_log_file = Path(f"{conf.LOG_DIR}/{project_id}.log")
#    if project_log_file.exists() and project_log_file.is_file():
#        console.pager(
#            project_log_file.read_text(),
#            status_bar_format=f"{project_log_file.resolve()} (status: {status})"
#        )
#    else:
#        console.error(
#            f"Error:\nLog file {project_log_file} not exists!",
#            hint=f"Check the device log file for possible errors"
#        )

@routers_cmd.command(short_help="Delete router\nAliases:[i] delete, rm")
@routers_cmd.command("rm", hidden=True)
def delete(
    ctx: typer.Context,
    router_address: Annotated[str, typer.Option("--router-address", help="router to remove")] = "",
    ):
    """
    Delete existing https router

    Aliases:[i] delete, rm
    """
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    def get_router(addr):
        with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
            return db.table('routers').get(Query().address == addr)

    with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
        routers_db = db.table('routers')
        routers_all = routers_db.all()
        if not len(routers_all):
            console.info("no proxies available.")
            raise typer.Exit()

        for router_to_delete in questionary.checkbox(
                f"Select the proxy(s) to be deleted?",
                choices=[r.get("address") for r in routers_all],
                ).ask():
            selected_router_cuid = get_router(router_to_delete).get("service_id")
            console.info(f"selected proxy to delete: {selected_router_cuid=}")
            assert(selected_router_cuid)

            # rm router configs
            #router = routers_db.get(Query().service_id == selected_router_cuid)

            selected_router_config_path = Path(conf.CONFIG_DIR) / \
                "projects" \
                / f"{selected_router_cuid}.json"
            console.info(f"{selected_router_config_path=}")

            if Path(selected_router_config_path).exists():
                selected_router_config_path.unlink(missing_ok=True)
                console.info(f"deleted router config @ {selected_router_cuid}")

            # rm router runtimes
            # note uwsgi vacuum should remove all of these
            #for file in path(conf.run_dir).iterdir():
            #    if selected_router_cuid in str(file.resolve()):
            #        file.unlink(missing_ok=true)
            #        console.info(f"deleted app run files @ {str(file)}")

            routers_db.remove(where('service_id') == selected_router_cuid)
            console.success(f"removed ssl proxy '{router_to_delete}' [{selected_router_cuid}]")

    """

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
    selected_project_config_path = Path(conf.CONFIG_DIR) / selected_project_cuid
    selected_project_config_path.with_suffix('.json').unlink(missing_ok=True)
    if Path(selected_project_config_path).exists():
        shutil.rmtree(str(selected_project_config_path.resolve()))

    # rm project runtimes
    for file in Path(conf.RUN_DIR).iterdir():
        if selected_project_cuid in str(file.resolve()):
            file.unlink(missing_ok=True)

    # rm project from db
    device_db.remove(where('cuid') == selected_project_cuid)

    console.success(f"Removed project '{selected_project_name}'!")
    """ 

app.add_typer(routers_cmd)
