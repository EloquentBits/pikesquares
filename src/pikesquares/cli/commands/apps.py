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

def create_venv(venv_dir):
    subprocess.run(
        args=[
            sys.executable,
            "-m",
            "venv",
            "--clear",
            str(venv_dir),
        ],
        check=True,
    )

def venv_pip_install(venv_dir: Path, service_id: str, *args: str, find_links: str | None) -> None:
    subprocess.run(
        args=[
            str(venv_dir / "bin" / "python"),
            "-sE",
            "-m",
            "pip",
            "--disable-pip-version-check",
            "--no-python-version-warning",
            "--log",
            str(venv_dir / f"{service_id}-pip-install.log"),
            "install",
            #"--quiet",
            *(("--find-links", find_links) if find_links else ()),
            *args,
        ],
        check=True,
    )


class NameValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a value",
                cursor_position=len(document.text),
            )

class RepoAddressValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a valid repo url",
                cursor_position=len(document.text),
            )

class PathValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a value",
                cursor_position=len(document.text),
            )
        if not Path(document.text).exists():
            raise questionary.ValidationError(
                message="Please enter an existing directory to clone your git repository into",
                cursor_position=len(document.text),
            )


class CloneProgress(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        #console.info(f"{op_code=} {cur_count=} {max_count=} {message=}")
        if message:
            console.info(f"Completed git clone {message}")
 
#validate=lambda text: True if len(text) > 0 else "Please enter a value"

#print(questionary.text("What's your name?", 
#    validate=lambda text: len(text) > 0).ask())

@apps_cmd.command(short_help="Create new app in project\nAliases: [i] create, new")
@apps_cmd.command("new", hidden=True)
def create(
    ctx: typer.Context,
    project: Optional[str] = typer.Option("", "--in", "--in-project", 
        help="Name or id of project to add new app"
    ),
    name: Annotated[str, typer.Option("--name", "-n", help="app name")] = "",
    source: Annotated[str, typer.Option("--source", "-s", help="app source")] = "",
    #app_type: Annotated[str, typer.Option("--app-type", "-t", help="app source")] =  "",
    router_address: Annotated[str, typer.Option("--router-address", "-r", help="ssl router address")] =  "",

    base_dir: Annotated[
        Optional[Path], 
        typer.Option(
            "--base-dir", 
            "-d", 
            exists=True,
            #file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
            help="app base directory",
        )
    ] = None,

    #runtime: Annotated[str, typer.Option("--runtime", "-r", help="app language runtime")] = "",
    runtime: Annotated[
        LanguageRuntime, 
        typer.Option(
            "--runtime", 
            "-r", 
            case_sensitive=False,
            help="app language runtime"
        )
    ] = LanguageRuntime.python,
):
    """
    Create new app in project

    Aliases: [i] create, new
    """
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    custom_style = obj.get("cli-style")

    app_options = dict()

    #console.error(
    #        "this is some kind of misunderstanding", 
    #        example="this is an example", 
    #        example_description="this is a description", 
    #        hint="this is a hint"
    #)

    provider = questionary.select(
            "Select a base directory or git repository directory for your app: ",
        choices=[
            "Git Repository",
            "Local Filesystem Directory",
            #"PikeSquares App Template",
            questionary.Separator(),
            questionary.Choice("PikeSquares App Template", disabled="coming soon"),
        ],
        style=custom_style,
        use_shortcuts=True,
        use_indicator=True,
        show_selected=True,
        instruction="this is an instruction",
    ).ask()
    if not provider:
        raise typer.Exit()

    base_dir:str = ""
    repo_name:str = ""
    if provider == "Local Filesystem Directory":
        base_dir = questionary.path(
                "Enter your app base directory: ", 
            default=os.getcwd(),
            only_directories=True,
            style=custom_style,
        ).ask()

    elif provider == "Git Repository":
        repo = None
        repo_url:str = ""

        def prompt_repo_url():
            return questionary.text(
                "Enter your app git repository url:", 
                default="",
                instruction="""\nExamples:\n    https://host.xz/path/to/repo.git\n    ssh://host.xz/path/to/repo.git\n""",
                style=custom_style,
                validate=RepoAddressValidator,
            ).ask()

        repo_url = prompt_repo_url()

        def prompt_base_dir(repo_name: str) -> Path:
            return questionary.path(
                    f"Choose a directory to clone your `{repo_name}` git repository into: ", 
                default=os.getcwd(),
                only_directories=True,
                style=custom_style,
                validate=PathValidator,
            ).ask()

        def get_repo_name_from_url(repo_url):
            str_pattern = ["([^/]+)\\.git$"]
            for i in range(len(str_pattern)):
                pattern = re.compile(str_pattern[i])
                matcher = pattern.search(repo_url)
                if matcher:
                    return matcher.group(1)

        repo_name:str = get_repo_name_from_url(repo_url) or ""
        if not repo_name:
            console.warning(f"The repository url `{repo_url}` is invalid. ")
            raise typer.Exit()

        base_dir: Path = prompt_base_dir(repo_name)
        clone_into_dir = Path(base_dir) / repo_name
        if clone_into_dir.exists() and any(clone_into_dir.iterdir()):
            clone_into_dir_files = list(clone_into_dir.iterdir())
            if clone_into_dir / ".git" in clone_into_dir_files:
                if not questionary.confirm(
                    f"There appears to be a git repository already cloned in {clone_into_dir}. Chose another directory?",
                    default=True,
                    auto_enter=True,
                    style=custom_style,
                ).ask():
                    raise typer.Exit()

                base_dir = prompt_base_dir(repo_name)

            elif len(clone_into_dir_files):
                if not questionary.confirm(
                    f"Directory {str(clone_into_dir)} is not emptry. Continue?",
                    default=True,
                    auto_enter=True,
                    style=custom_style,
                ).ask():
                    raise typer.Exit()

        #console.info(f"cloning `{repo_name}` repository into `{clone_into_dir}`")

        with console.status(f"cloning `{repo_name}` repository into `{clone_into_dir}`", spinner="earth"):
            while not repo:
                try:
                    repo = git.Repo.clone_from(repo_url, clone_into_dir,  progress=CloneProgress())
                except git.GitCommandError as exc:
                    print(traceback.format_exc())
                    if "already exists and is not an empty directory" in exc.stderr:
                        if questionary.confirm(
                                "Continue with this directory?",
                                instruction=f"A git repository exists at {base_dir}",
                                default=True,
                                auto_enter=True,
                                style=custom_style,
                                ).ask():
                            break
                        base_dir = prompt_base_dir(repo_name)
                    elif "Repository not found" in exc.stderr:
                        console.warning(f"unable to locate a git repository at {repo_url}")
                        repo_url = prompt_repo_url()
                        if not repo_url:
                            raise typer.Exit()
                    else:
                        console.warning(f"error: unable to clone a git repository at {repo_url}")
                        console.warning(f"{exc.stdout}")
                        console.warning(f"{exc.stderr}")
                        repo_url = prompt_repo_url()
                        if not repo_url:
                            raise typer.Exit()
        if repo:
            #repo_working_dir = repo.working_dir
            base_dir = str(clone_into_dir)

    elif provider == "PikeSquares App Template":
        pass
    else:
        console.warning("invalid app source")
        raise typer.Exit()

    app_options["root_dir"] = base_dir

    base_dir_name = str(Path(base_dir).name) if base_dir else None
    name = name or questionary.text(
        "Choose a name for your app: ", 
        default=repo_name or base_dir_name  or randomname.get_name(),
        style=custom_style,
        validate=NameValidator,
    ).ask()

    if not name:
        raise typer.Exit()

    #DISABLED = True
    #response = questionary.confirm("Are you amazed?").skip_if(DISABLED, default=True).ask()

    project_id = None
    with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
        projects = db.table('projects').all()
        if len(projects) == 1:
            project = "sandbox"
        else:
            project = project or questionary.select(
                    "Select project where you want to create app: ", 
                    choices=[p.get("name") for p in projects],
                    style=custom_style,
                    ).ask()
        project_id = db.table('projects').get(Query().name == project).get("service_id")

    if not all([project, project_id]):
        raise typer.Exit()

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

    # APP Type
    #service_type = console.choose(
    #    "What type of app would you like to create?",
    #    choices=HandlerFactory.user_visible_apps(),
    #)
    service_type = "WSGI-App"
    # service ID
    service_type_prefix = service_type.replace('-', '_').lower()
    service_id = f"{service_type_prefix}_{cuid()}"

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

    app_options["wsgi_file"] = str(Path(base_dir) / wsgi_file)

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
            choices=pip_req_files + [
                questionary.Separator(),
                CHOSE_FILE_MYSELF
            ],
            style=custom_style,
        ).ask()
        if pip_req_file == CHOSE_FILE_MYSELF:
            pip_req_file = pip_req_file_q.ask()
    else:
        pip_req_file = pip_req_file_q.ask()

    pip_req_file_path = Path(base_dir) / pip_req_file
    if pip_req_file_path.exists():
        venv_dir = Path(conf.DATA_DIR) / "venvs" / service_id
        create_venv(venv_dir)
        if not venv_dir.exists():
            console.warning("unable to create python virtualenv")
            raise typer.Exit()
        app_options["pyvenv_dir"] = str(venv_dir)
        app_reqs = list(filter(None, pip_req_file_path.read_text().split("\n")))
        console.info(f"installing app dependencies")
        venv_pip_install(venv_dir, service_id, "--progress-bar", "on", *app_reqs, find_links=None)

    # Router
    def get_router(addr):
        with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
            return db.table('routers').get(Query().address == addr)

    router_id = None
    if not router_address:
        router_address = questionary.select(
            "Select an ssl proxy for your app: ", 
            choices=[r.get("address") for r in https_routers_all(conf)],
            style=custom_style,
            ).ask()
    try:
        router_id = get_router(router_address).get("service_id")
    except IndexError:
        console.warning(f"unable to locate router at address [{router_address}]")
        raise typer.Exit()
    #print(f"Selected Https Routers: {router_id} running on: {router_address}")
    app_options["router_id"] = router_id
    #print(app_options)


    #console.info(app_options)
    app_options["workers"] = 3


    with console.status(f"`{name}` is starting...", spinner="earth"):
        wsgi_app_up(
            conf,
            name,
            service_id,
            project_id,
            **app_options,
        )

        try:
            router_port = router_address.split(':')[-1]
        except IndexError:
            pass
        else:
            url = console.render_link(f'{name}.pikesquares.dev', port=router_port)
            for _ in range(10):
                if get_service_status(
                    (Path(conf.RUN_DIR) / f"{service_id}-stats.sock")) == "running":
                    console.success(f"App is available at {url}")
                    raise typer.Exit()
                time.sleep(3)

            app_config = Path(conf.CONFIG_DIR) / project_id / "apps" / f"{service_id}.json"
            app_config.unlink()
            console.warning(f"could not start app. giving up.")
            console.info(f"removed app config {app_config}")


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
