import time
import traceback
import os
from pathlib import Path
from typing import Optional, Tuple
from glob import glob

import typer
from typing_extensions import Annotated
import git
from tinydb import TinyDB, where, Query
import questionary
import randomname
from cuid import cuid

from pikesquares.services import HandlerFactory
#from pikesquares.services.router import https_routers_all
from pikesquares.services import WsgiApp

from .validators import (
    NameValidator, 
    PathValidator,
)
from . import (
    #apps_cmd,
    LanguageRuntime, 
    CHOSE_FILE_MYSELF,
    create_venv,
    venv_pip_install,
    gather_repo_details,
)
from ...console import console


class CloneProgress(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        #console.info(f"{op_code=} {cur_count=} {max_count=} {message=}")
        if message:
            console.info(f"Completed git clone {message}")
 
#validate=lambda text: True if len(text) > 0 else "Please enter a value"
#print(questionary.text("What's your name?", 
#    validate=lambda text: len(text) > 0).ask())


app = typer.Typer()

@app.command(short_help="Create new app in project\nAliases: [i] create, new")
@app.command("new", hidden=True)
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
    custom_style = obj.get("cli-style")
    app_options = dict()

    # APP Type
    #service_type = console.choose(
    #    "What type of app would you like to create?",
    #    choices=HandlerFactory.user_visible_apps(),
    #)
    service_type = "WSGI-App"
    # service ID
    service_type_prefix = service_type.replace('-', '_').lower()
    service_id = f"{service_type_prefix}_{cuid()}"

    #console.error(
    #        "this is some kind of misunderstanding", 
    #        example="this is an example", 
    #        example_description="this is a description", 
    #        hint="this is a hint"
    #)

    provider = questionary.select(
            "Select the location of your app codebase: ",
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
        show_selected=False,
        #instruction="this is an instruction",
    ).ask()
    if not provider:
        raise typer.Exit()

    base_dir:Path
    repo_name:str = ""
    repo_url:str = ""
    if provider == "Local Filesystem Directory":
        base_dir = Path(questionary.path(
                "Enter your app base directory: ", 
            default=os.getcwd(),
            only_directories=True,
            validate=PathValidator,
            style=custom_style,
        ).ask())

    elif provider == "Git Repository":

        def gather_repo_details_and_clone() -> Tuple[str, str, Path]:
            repo = None
            repo_url, repo_name, clone_into_dir = gather_repo_details(custom_style)

            def try_again_q(instruction):
                return questionary.confirm(
                        "Try entring a different repository url?",
                        instruction=instruction,
                        default=True,
                        auto_enter=True,
                        style=custom_style,
                )
            with console.status(f"cloning `{repo_name}` repository into `{clone_into_dir}`", spinner="earth"):
                while not repo:
                    try:
                        repo = git.Repo.clone_from(repo_url, clone_into_dir,  progress=CloneProgress())
                    except git.GitCommandError as exc:
                        if "already exists and is not an empty directory" in exc.stderr:
                            if questionary.confirm(
                                    "Continue with this directory?",
                                    instruction=f"A git repository exists at {clone_into_dir}",
                                    default=True,
                                    auto_enter=True,
                                    style=custom_style,
                                    ).ask():
                                break
                            #base_dir = prompt_base_dir(repo_name, custom_style)
                        elif "Repository not found" in exc.stderr:
                            if try_again_q(f"Unable to locate a git repository at {repo_url}").ask():
                                gather_repo_details_and_clone()
                            raise typer.Exit()
                        else:
                            console.warning(traceback.format_exc())
                            console.warning(f"{exc.stdout}")
                            console.warning(f"{exc.stderr}")
                            if try_again_q("Unable to clone the provided repository url at {repo_url}").ask():
                                gather_repo_details_and_clone()
                            raise typer.Exit()

            return repo_url, repo_name, clone_into_dir 

        repo_url, repo_name, clone_into_dir = gather_repo_details_and_clone()
        #repo_working_dir = repo.working_dir
        base_dir = clone_into_dir

    elif provider == "PikeSquares App Template":
        pass
    else:
        console.warning("invalid app source")
        raise typer.Exit()

    app_options["root_dir"] = str(base_dir)
    name = name or questionary.text(
        "Choose a name for your app: ", 
        default=repo_name or base_dir.name or randomname.get_name(),
        style=custom_style,
        validate=NameValidator,
    ).ask()

    if not name:
        raise typer.Exit()

    wsgi_app_handler = HandlerFactory.make_handler("WSGI-App")(
        WsgiApp(name=name, service_id=service_id)
    )

    #DISABLED = True
    #response = questionary.confirm("Are you amazed?").skip_if(DISABLED, default=True).ask()

    project_id = None
    with TinyDB(wsgi_app_handler.svc_model.device_db_path) as db:
        projects = db.table('projects').all()
        if len(projects) == 1:
            project = "sandbox"
        else:
            project = project or questionary.select(
                    "Select project where you want to create app: ", 
                    choices=[p.get("name") for p in projects],
                    style=custom_style,
                    ).ask()
        project_id = db.table('projects').\
            get(Query().name == project).get("service_id")

    if not all([project, project_id]):
        raise typer.Exit()

    wsgi_app_handler.svc_model.parent_service_id = project_id

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

    app_options["wsgi_file"] = str(base_dir / wsgi_file)

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

    pip_req_file_path = base_dir / pip_req_file
    if pip_req_file_path.exists():

        with console.status(f"creating a Python venv and installing dependencies", spinner="earth"):
            venv_dir = wsgi_app_handler.svc_model.data_dir / "venvs" / service_id
            create_venv(venv_dir)
            console.info(f"created venv")
            if not venv_dir.exists():
                console.warning("unable to create python virtualenv")
                raise typer.Exit()
            app_options["pyvenv_dir"] = str(venv_dir)
            app_reqs = list(filter(None, pip_req_file_path.read_text().split("\n")))
            console.info(f"installing app dependencies")
            venv_pip_install(venv_dir, service_id, "--progress-bar", "off", *app_reqs, find_links=None)
            console.info(f"done installing dependencies")

    # Router
    def get_router(addr):
        with TinyDB(wsgi_app_handler.svc_model.device_db_path) as db:
            return db.table('routers').get(Query().address == addr)

    router_id = None
    if not router_address:
        with TinyDB(wsgi_app_handler.svc_model.device_db_path) as db:
            routers_db = db.table('routers')
            router_address = questionary.select(
                "Select an ssl proxy for your app: ", 
                choices=[r.get("address") for r in routers_db.all()],
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
        wsgi_app_handler.prepare_service_config(**app_options)
        wsgi_app_handler.connect()
        wsgi_app_handler.start()

        try:
            router_port = router_address.split(':')[-1]
        except IndexError:
            pass
        else:
            url = console.render_link(f'{name}.pikesquares.dev', port=router_port)
            for _ in range(10):
                if wsgi_app_handler.svc_model.get_service_status() == "running":
                    console.success(f"App is available at {url}")
                    raise typer.Exit()
                time.sleep(3)

            wsgi_app_handler.svc_model.service_config.unlink()
            console.warning(f"could not start app. giving up.")
            console.info(f"removed app config {wsgi_app_handler.svc_model.service_config.name}")


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

if __name__ == "__main__":
    app()
