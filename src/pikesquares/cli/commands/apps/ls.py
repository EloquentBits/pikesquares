from pathlib import Path

import typer
from tinydb import TinyDB, where, Query
import questionary

from pikesquares.services.project import projects_all
from pikesquares import (
    get_service_status, 
    read_stats,
    #get_first_available_port,
)
from ...console import console

app = typer.Typer()

@app.command(
    "apps",
    rich_help_panel="Show",
    short_help="Show all apps in specific project.\nAliases:[i] apps, app list"
)
@app.command("proj", rich_help_panel="Show", hidden=True)
@app.command("list")
def list(
    ctx: typer.Context,
    project: str = typer.Argument("", help="Project name"),
    show_id: bool = False
):
    """
    Show all apps in specific project

    Aliases:[i] apps, app list
    """
    
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")
    custom_style = obj.get("cli-style")

    #if not project:
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
        with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
            return db.table('projects').get(Query().name == project)

    project_id = None
    if not project:
        project = questionary.select(
            "Select project: ", 
            choices=[p.get("name") for p in projects_all(conf)],
            style=custom_style,
            ).ask()
        project_id = get_project_id(project).get("service_id")
        assert project_id
    else:
        project_id = get_project_id(project)

    with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
        apps_out = []
        for app in db.table('apps').search(where('project_id') == project_id):
            service_id = app.get("service_id")
            stats_socket = Path(conf.RUN_DIR) / f"{service_id}-stats.sock"
            print(read_stats(str(stats_socket)))
            print(f"{stats_socket=} {service_id=}")
            status = get_service_status(
                (Path(conf.RUN_DIR) / f"{service_id}-stats.sock")
            )
            apps_out.append({
                'name': app.get('name'),
                'status': status or "uknown", 
                'id': service_id,
            })
        if not apps_out:
            console.info("You have not created any apps yet.")
            console.info("Create apps using the `pikesquares apps create` command")
        else:
            console.print_response(
                apps_out, 
                title=f"Apps in project '{project}'", 
                show_id=show_id, 
                exclude=['parent_id', 'options']
            )

