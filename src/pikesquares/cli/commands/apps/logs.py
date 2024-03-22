from pathlib import Path
from typing import Optional

import typer
#from typing_extensions import Annotated
from tinydb import TinyDB, where, Query
import questionary

#from pikesquares.services.project import projects_all
from pikesquares import (
    get_service_status, 
    #read_stats,
    #get_first_available_port,
)
from ...console import console

app = typer.Typer()

@app.command("logs", short_help="Show app logs")
def logs(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Argument(""),
    app_id: Optional[str] = typer.Argument("")
):

    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    if not project_id:
        available_projects = {p.get("name"): p.get("cuid") for p in obj['projects']()}
        if not available_projects:
            console.warning(f"No projects were created, create at least one project first!")
            raise typer.Exit()
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

    status = get_service_status(f"{app_id}", conf)

    project_log_file = Path(f"{conf.LOG_DIR}/{project_id}.log")
    app_log_file = Path(f"{conf.LOG_DIR}/{app_id}.log")
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
