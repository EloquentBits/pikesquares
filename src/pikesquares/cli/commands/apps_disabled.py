import traceback
import sys
import re
import time
import subprocess
import os
from glob import glob
from pathlib import Path
from typing import Optional
from enum import Enum

from tinydb import TinyDB, where, Query
import git
import typer
from typing_extensions import Annotated
import randomname
import questionary
from cuid import cuid

from rich.console import Group
from rich.panel import Panel
from rich.live import Live
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from pikesquares import (
    get_service_status, 
    read_stats,
    #get_first_available_port,
)

from pikesquares.services import (
    HandlerFactory, 
)

from pikesquares.services.app import (
    wsgi_app_up,
    apps_all,
)

from pikesquares.services.project import projects_all
from pikesquares.services.router import https_routers_all

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


class LanguageRuntime(str, Enum):
    python = "python"
    ruby = "ruby"
    php = "php"
    perl = "perl"

CHOSE_FILE_MYSELF = "-- Select the file myself --"

def run_steps(name, step_times, app_steps_task_id):
    """Run steps for a single app, and update corresponding progress bars."""

    for idx, step_time in enumerate(step_times):
        # add progress bar for this step (time elapsed + spinner)
        action = step_actions[idx]
        step_task_id = step_progress.add_task("", action=action, name=name)

        # run steps, update progress
        for _ in range(step_time):
            time.sleep(0.5)
            step_progress.update(step_task_id, advance=1)

        # stop and hide progress bar for this step when done
        step_progress.stop_task(step_task_id)
        step_progress.update(step_task_id, visible=False)

        # also update progress bar for current app when step is done
        app_steps_progress.update(app_steps_task_id, advance=1)


# progress bar for current app showing only elapsed time,
# which will stay visible when app is installed
current_app_progress = Progress(
    TimeElapsedColumn(),
    TextColumn("{task.description}"),
)

# progress bars for single app steps (will be hidden when step is done)
step_progress = Progress(
    TextColumn("  "),
    TimeElapsedColumn(),
    TextColumn("[bold purple]{task.fields[action]}"),
    SpinnerColumn("simpleDots"),
)
# progress bar for current app (progress in steps)
app_steps_progress = Progress(
    TextColumn(
        "[bold blue]Progress for app {task.fields[name]}: {task.percentage:.0f}%"
    ),
    BarColumn(),
    TextColumn("({task.completed} of {task.total} steps done)"),
)
# overall progress bar
overall_progress = Progress(
    TimeElapsedColumn(), BarColumn(), TextColumn("{task.description}")
)
# group of progress bars;
# some are always visible, others will disappear when progress is complete
progress_group = Group(
    Panel(Group(current_app_progress, step_progress, app_steps_progress)),
    overall_progress,
)

# tuple specifies how long each step takes for that app
step_actions = ("downloading", "configuring", "building", "installing")
apps = [
    ("one", (2, 1, 4, 2)),
    ("two", (1, 3, 8, 4)),
    ("three", (2, 1, 3, 2)),
]

# create overall progress bar
overall_task_id = overall_progress.add_task("", total=len(apps))

# use own live instance as context manager with group of progress bars,
# which allows for running multiple different progress bars in parallel,
# and dynamically showing/hiding them
if 0:
    with Live(progress_group):
        for idx, (name, step_times) in enumerate(apps):
            # update message on overall progress bar
            top_descr = "[bold #AAAAAA](%d out of %d apps installed)" % (idx, len(apps))
            overall_progress.update(overall_task_id, description=top_descr)

            # add progress bar for steps of this app, and run the steps
            current_task_id = current_app_progress.add_task("Installing app %s" % name)
            app_steps_task_id = app_steps_progress.add_task(
                "", total=len(step_times), name=name
            )
            run_steps(name, step_times, app_steps_task_id)

            # stop and hide steps progress bar for this specific app
            app_steps_progress.update(app_steps_task_id, visible=False)
            current_app_progress.stop_task(current_task_id)
            current_app_progress.update(
                current_task_id, description="[bold green]App %s installed!" % name
            )

            # increase overall progress now this task is done
            overall_progress.update(overall_task_id, advance=1)

        # final update for message on overall progress bar
        overall_progress.update(
            overall_task_id, description="[bold green]%s apps installed, done!" % len(apps)
        )

@app.command(
    "apps",
    rich_help_panel="Show",
    short_help="Show all apps in specific project.\nAliases:[i] apps, app list"
)
@app.command("proj", rich_help_panel="Show", hidden=True)
@apps_cmd.command("list")
def list_(
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


#@apps_cmd.command("logs", short_help="Show app logs")
#def logs(
#    ctx: typer.Context,
#    project_id: Optional[str] = typer.Argument(""),
#    app_id: Optional[str] = typer.Argument("")
#):

#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    if not project_id:
#        available_projects = {p.get("name"): p.get("cuid") for p in obj['projects']()}
#        if not available_projects:
#            console.warning(f"No projects were created, create at least one project first!")
#            raise typer.Exit()
#        project_name = console.choose("Choose project which you want to view logs:", choices=available_projects)
#        project_id = available_projects.get(project_name)
    
#    project_db = obj['project'](project_name)

#    if not app_id:
#        apps = {
#            a.get("name"): a.get("cuid")
#            for a in project_db.get(where('name') == project_name).get('apps')
#        }
#        app_name = console.choose("Choose app you want to view logs:", choices=apps)
#        app_id = apps.get(app_name)

#    status = get_service_status(f"{app_id}", conf)

#    project_log_file = Path(f"{conf.LOG_DIR}/{project_id}.log")
#    app_log_file = Path(f"{conf.LOG_DIR}/{app_id}.log")
#    if app_log_file.exists() and app_log_file.is_file():
#        console.pager(
#            app_log_file.read_text(),
#            status_bar_format=f"{app_log_file.resolve()} (status: {status})"
#        )
#    else:
#        console.error(
#            f"Error:\nLog file {app_log_file} not exists!",
#            hint=f"Check the project log file {project_log_file} for possible errors"
#        )

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
    conf = obj.get("conf")

    if not project_id:
        available_projects = {p.get('name'): p.get('cuid') for p in obj['projects']()}
        if not available_projects:
            console.warning(f"No projects were created, create at least one project first!")
            raise typer.Exit()
        project_name = console.choose("Select project where you want to start app", choices=available_projects)
        project_id = available_projects.get(project_name)

    project_db = obj['project'](project_name)
    
    apps = {a.get('name'): a for a in project_db.get(where('name') == project_name).get('apps')}
    if not apps:
        console.warning(f"No apps were created in this project, create at least one app first!")
        raise typer.Exit()

    if not app_name:
        app_name = console.choose("Select app you want to start in this project", choices=apps)

    app_ent = apps.get(app_name)
    if not app_ent:
        console.error(f"Application with name '{app_name}' does not exists!")
        raise typer.Exit()

    app_id = app_ent.get('cuid')
    app_type = app_ent.get('type')
    app_root_dir = app_ent.get('path')
    app_opts = app_ent.get('options', {})
    if app_type == "Project":
        console.error(
            "You've entered project name instead of app name!",
            example=f"vc projects start '{app_name}'"
        )
        raise typer.Exit()

    app = HandlerFactory.make_handler(app_type)(
        service_id=app_id,
        conf=conf,
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
    conf = obj.get("conf")

    if not project_id:
        available_projects = {p.get('name'): p.get('cuid') for p in obj['projects']()}
        if not available_projects:
            console.warning(f"No projects were created, create at least one project first!")
            raise typer.Exit()
        project_name = console.choose("Select project where you want to stop app", choices=available_projects)
        project_id = available_projects.get(project_name)

    project_db = obj['project'](project_name)
    
    apps = {a.get('name'): a for a in project_db.get(where('name') == project_name).get('apps')}
    if not apps:
        console.warning(f"No apps were created in this project, create at least one app first!")
        raise typer.Exit()

    if not app_name:
        app_name = console.choose("Select app you want to stop in this project", choices=apps)

    app_ent = apps.get(app_name)
    if not app_ent:
        console.error(f"Application with name '{app_name}' does not exists!")
        raise typer.Exit()

    app_id = app_ent.get('cuid')
    app_type = app_ent.get('type')
    if app_type == "Project":
        console.error(
            "You've entered project name instead of app name!",
            example=f"vc projects stop '{app_name}'"
        )
        raise typer.Exit()

    app = HandlerFactory.make_handler(app_type)(
        service_id=app_id,
        parent_service_id=project_id,
        conf=conf,
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

app.add_typer(apps_cmd)
