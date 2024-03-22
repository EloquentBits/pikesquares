from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated
from tinydb import TinyDB, where, Query
import questionary

from ...console import console

app = typer.Typer()

@app.command(short_help="Delete existing app by name or id\nAliases:[i] delete, rm")
@app.command("rm", hidden=True)
def delete(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Option("--name", "-n", help="Name of app to delete")] = "",
    proj_name: Optional[str] = typer.Option("", "--from", help="Name of project to delete app"),
):
    """
    Delete existing app by name or id

    Aliases:[i] delete, rm
    """
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")
    custom_style = obj.get("cli-style")

    #if not proj_name:
    #    available_projects = {p.get("name"): p.get("cuid") for p in obj['projects']()}
    #    if not available_projects:
    #        console.warning(f"No projects were created, create at least one project first!")
    #        return
    #    proj_name = console.choose("Choose project where you want to delete app:", choices=available_projects)

    #project_db = obj['project'](proj_name)

    #apps_choices = {
    #    k.get('name'): k.get('cuid')
    #    for k in project_db.get(where('name') == proj_name).get('apps')
    #}
    #if not apps_choices:
    #    console.warning(f"No apps were initialized in project '{proj_name}', nothing to delete!")
    #    return

    #print(apps_choices)

    selected_app_cuid = None
    
    if not app_name:
        def get_app(app: str):
            with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
                return db.table('apps').get(Query().name == app)

        with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
            apps_db = db.table('apps')
            apps_all = apps_db.all()
            if not len(apps_all):
                console.info("no apps available.")
                raise typer.Exit()

            for app_to_delete in questionary.checkbox(
                    f"Select the app(s) to be deleted?",
                    choices=[f"{p.get('name')} [{p.get('service_id')}]" for p in apps_all],
                    style=custom_style,
                    ).ask():
                selected_app_cuid = get_app(app_to_delete).get("service_id")
                #console.info(f"selected app to delete: {selected_app_cuid=}")
                assert(selected_app_cuid)

                # rm app configs
                app = apps_db.get(Query().service_id == selected_app_cuid)
                project_id = app.get("project_id")

                # FIXME use cuid instread of app name
                selected_app_config_path = Path(conf.CONFIG_DIR) / \
                    f"{project_id}" / "apps" \
                    / f"{selected_app_cuid}.json"

                if Path(selected_app_config_path).exists():
                    selected_app_config_path.unlink(missing_ok=True)
                    console.info(f"deleted app config @ {selected_app_cuid}")

                # rm app runtimes
                # NOTE uwsgi vacuum should remove all of these
                #for file in Path(conf.RUN_DIR).iterdir():
                #    if selected_app_cuid in str(file.resolve()):
                #        file.unlink(missing_ok=True)
                #        console.info(f"deleted app run files @ {str(file)}")

                apps_db.remove(where('service_id') == selected_app_cuid)
                console.success(f"Removed app '{app_to_delete}' [{selected_app_cuid}]")

