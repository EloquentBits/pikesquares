import time
import os
import traceback
import sys
import subprocess
from pathlib import Path
from enum import Enum
from typing_extensions import Annotated
from typing import Optional
from glob import glob

import typer
import git
import questionary
import giturlparse
import randomname
from cuid import cuid
from tinydb import TinyDB, where, Query

from .validators import (
    RepoAddressValidator,
    PathValidator,
    # NameValidator,
)

from pikesquares import services, get_first_available_port
from pikesquares.services import device

from .validators import (
    NameValidator, 
    PathValidator,
)
from ...console import console


class LanguageRuntime(str, Enum):
    python = "python"
    ruby = "ruby"
    php = "php"
    perl = "perl"


CHOSE_FILE_MYSELF = "-- Select the file myself --"


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
            "--quiet",
            *(("--find-links", find_links) if find_links else ()),
            *args,
        ],
        check=True,
    )


def prompt_base_dir(repo_name: str, custom_style:questionary.Style) -> Path:
    return questionary.path(
            f"Choose a directory to clone your `{repo_name}` git repository into: ", 
        default=os.getcwd(),
        only_directories=True,
        style=custom_style,
        validate=PathValidator,
    ).ask()

def prompt_repo_url(custom_style:questionary.Style) -> str:
    repo_url_q = questionary.text(
            "Enter your app git repository url:", 
            default="",
            instruction="""\nExamples:\n    https://host.xz/path/to/repo.git\n    ssh://host.xz/path/to/repo.git\n>>>""",
            style=custom_style,
            validate=RepoAddressValidator,
    )
    if not repo_url_q:
        raise typer.Exit()
    return repo_url_q.ask()


class CloneProgress(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=""):
        # console.info(f"{op_code=} {cur_count=} {max_count=} {message=}")
        if message:
            console.info(f"Completed git clone {message}")


def gather_repo_details(custom_style: questionary.Style) -> tuple[str, str, Path]:
    repo_url = prompt_repo_url(custom_style)
    giturl = giturlparse.parse(repo_url)
    base_dir = prompt_base_dir(giturl.name, custom_style)
    clone_into_dir = Path(base_dir) / giturl.name
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
            return giturl.name, repo_url, prompt_base_dir(giturl.name, custom_style)
        elif len(clone_into_dir_files):
            if not questionary.confirm(
                f"Directory {str(clone_into_dir)} is not emptry. Continue?",
                default=True,
                auto_enter=True,
                style=custom_style,
            ).ask():
                raise typer.Exit()

    return repo_url, giturl.name, clone_into_dir


def provision_base_dir(custom_style):
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

    if provider == "Local Filesystem Directory":
        return Path(questionary.path(
                "Enter your app base directory: ", 
            default=os.getcwd(),
            only_directories=True,
            validate=PathValidator,
            style=custom_style,
        ).ask())

    elif provider == "Git Repository":

        def gather_repo_details_and_clone() -> Path:
            repo = None
            repo_url, _, clone_into_dir = gather_repo_details(custom_style)

            def try_again_q(instruction):
                return questionary.confirm(
                        "Try entring a different repository url?",
                        instruction=instruction,
                        default=True,
                        auto_enter=True,
                        style=custom_style,
                )
            #with console.status(f"cloning `{repo_name}` repository into `{clone_into_dir}`", spinner="earth"):
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
                        if try_again_q(f"Unable to clone the provided repository url at {repo_url} into {clone_into_dir}").ask():
                            gather_repo_details_and_clone()
                        raise typer.Exit()

            return clone_into_dir 

        return gather_repo_details_and_clone()

    elif provider == "PikeSquares App Template":
        pass
    else:
        console.warning("invalid app source")
        raise typer.Exit()


#validate=lambda text: True if len(text) > 0 else "Please enter a value"
#print(questionary.text("What's your name?", 
#    validate=lambda text: len(text) > 0).ask())

app = typer.Typer()


@app.command(short_help="Create new app\nAliases: [i] create, new")
@app.command()
def create(
    ctx: typer.Context,
    project: Optional[str] = typer.Option("", "--in", "--in-project",
        help="Name or id of project to add new app"
    ),
    name: Annotated[str, typer.Option("--name", "-n", help="app name")] = "",
    source: Annotated[str, typer.Option("--source", "-s", help="app source")] = "",
    # app_type: Annotated[str, typer.Option("--app-type", "-t", help="app source")] =  "",
    # router_address: Annotated[str, typer.Option("--router-address", "-r", help="ssl router address")] =  "",

    base_dir: Annotated[
        Path | None,
        typer.Option(
            "--base-dir",
            "-d",
            exists=True,
            # file_okay=True,
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
    #    choices=services.HandlerFactory.user_visible_apps(),
    #)
    service_type = "WSGI-App"
    # service ID
    service_type_prefix = service_type.replace('-', '_').lower()
    service_id = f"{service_type_prefix}_{cuid()}"

    base_dir = base_dir or provision_base_dir(custom_style)
    app_options["root_dir"] = str(base_dir)
    name = name or questionary.text(
        "Choose a name for your app: ", 
        default=randomname.get_name(),
        style=custom_style,
        validate=NameValidator,
    ).ask()

    if not name:
        raise typer.Exit()

    wsgi_app_handler = services.HandlerFactory.make_handler("WSGI-App")(
        services.WsgiApp(name=name, service_id=service_id)
    )

    project_id = None
    project_name = None
    with TinyDB(wsgi_app_handler.svc_model.device_db_path) as db:
        projects = db.table('projects').all()

        if not projects:
            project_name = "sandbox"
            project_handler = services.HandlerFactory.make_handler("Project")(
                services.Project(service_id="project_sandbox")
            )
            project_handler.up(project_name)
            cnt = 0
            while cnt < 5 and project_handler.svc_model.get_service_status() != "running":
                time.sleep(3)
                cnt = cnt+1
            if project_handler.svc_model.get_service_status() != "running":
                project_handler.svc_model.service_config.unlink()
                console.warning(f"could not start project. giving up.")
                console.info(f"removed sandbox project config {project_handler.svc_model.service_config.name}")
                raise typer.Exit()
            project_id = "project_sandbox"

        elif len(projects) == 1:
            project_name = "sandbox"
            project_id = "project_sandbox"
        else:
            project_name = project or questionary.select(
                    "Select project where you want to create app: ", 
                    choices=[p.get("name") for p in projects],
                    style=custom_style,
                    ).ask()
    if not project_id:
        with TinyDB(wsgi_app_handler.svc_model.device_db_path) as db:
            project_id = db.table('projects').\
                get(Query().name == project_name).get("service_id")

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
        #with console.status(f"creating a Python venv and installing dependencies", spinner="earth"):
        venv_dir = wsgi_app_handler.svc_model.data_dir / "venvs" / service_id
        create_venv(venv_dir)
        console.info(f"Created a Python virtualenv")
        if not venv_dir.exists():
            console.warning("unable to create python virtualenv")
            raise typer.Exit()
        app_options["pyvenv_dir"] = str(venv_dir)
        app_reqs = list(filter(None, pip_req_file_path.read_text().split("\n")))
        console.info(f"Installing app dependencies")
        venv_pip_install(venv_dir, service_id, "--progress-bar", "off", *app_reqs, find_links=None)

    # Router 
    router_id = None
    with TinyDB(wsgi_app_handler.svc_model.device_db_path) as db:
        routers_db = db.table('routers')

        def build_app_url(name: str, address: str) -> str:
            router_port = address.split(':')[-1]
            protocol = "http" if router_port.startswith("9") else "https"
            return f"{protocol}://{name}.pikesquares.dev:{router_port}"

        #def build_router_address(app_url: str) -> str:
        #    router_port = app_url.split(":")[-1]
        #    protocol = "http" if router_port.startswith("9") else "https"
        #    return f"{protocol}://0.0.0.0:{router_port}"

        def prompt_routers_q():
            app_url_choices = []
            contains_https_router = False
            for r in routers_db.all():
                app_url_choices.append(
                    questionary.Choice(
                        build_app_url(name, r.get("address")),
                        value=r.get("address"),
                        checked=False,
                    )
                )
                if r.get("address").split(":")[-1].startswith('8'):
                    contains_https_router = True
            if not app_url_choices:
                http_router_addr = f"0.0.0.0:{str(get_first_available_port(port=9000))}"
                app_url_choices.append(
                    questionary.Choice(
                        build_app_url(name, http_router_addr),
                        value=http_router_addr,
                        checked=False,
                    )
                )
            if not contains_https_router:
                https_router_addr = f"0.0.0.0:{str(get_first_available_port(port=8443))}"
                app_url_choices.append(
                    questionary.Choice(
                        build_app_url(name, https_router_addr),
                        value=https_router_addr,
                        checked=False,
                    )
                )
            return questionary.select(
                "Select a Virtual Host URL for your app: ", 
                app_url_choices,
                instruction="" if contains_https_router else "pki install instructions",
                style=custom_style,
                )

        router_address = prompt_routers_q().ask()
        if not router_address:
            raise typer.Exit()

        router = routers_db.get(Query().address == router_address)
        router_id = router.get("service_id") if router else f"router_{cuid()}"
        app_options["router_id"] = router_id

        router_class = None
        router_handler_name = None
        if router_address.split(":")[-1].startswith("8"):
            router_handler_name = "Https-Router"
            router_class = services.HttpsRouter

        if router_address.split(":")[-1].startswith("9"):
            router_handler_name = "Http-Router"
            router_class = services.HttpRouter

        if router_handler_name and router_class:
            router_handler = services.HandlerFactory.make_handler(router_handler_name)(
                router_class(service_id=router_id)
            )
            router_handler.up(router_address)
            cnt = 0
            while cnt < 5 and router_handler.svc_model.get_service_status() != "running":
                time.sleep(3)
                cnt = cnt+1
            if router_handler.svc_model.get_service_status() != "running":
                router_handler.svc_model.service_config.unlink()
                console.warning(f"could not start {router_handler_name}. giving up.")
                console.info(f"removed proxy config {router_handler.svc_model.service_config.name}")
                raise typer.Exit()
            console.success(f"{router_handler_name} is up")

    console.info(app_options)
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
            url = console.render_link(
                f'{name}.pikesquares.dev', 
                port=router_port,
                protocol="http" if router_port.startswith("9") else "https"
            )
            for _ in range(10):
                if wsgi_app_handler.svc_model.get_service_status() == "running":
                    console.success(f"🚀 App is available at {url}")
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


@app.command(
    short_help="Show all apps in specific project.\nAliases:[i] apps, app list"
)
@app.command()
def ls(
    ctx: typer.Context,
    project: str = typer.Argument("", help="Project name"),
    show_id: bool = False,
):
    """
    Show all apps in specific project

    Aliases:[i] apps, app list
    """
    context = ctx.ensure_object(dict)
    # device_handler = obj.get("device-handler")
    custom_style = context.get("cli-style")

    db = services.get(context, TinyDB)
    # device_handler = services.get(obj, device.DeviceService)

    # if not project:
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
        return db.table('projects').get(Query().name == project)

    project_id = None
    if not project:
        projects_db = db.table('projects')
        project = questionary.select(
            "Select project: ", 
            choices=[p.get("name") for p in projects_db.all()],
            style=custom_style,
            ).ask()
        project_id = get_project_id(project).get("service_id")
        assert project_id
    else:
        project_id = get_project_id(project)

    apps_out = []
    for app in db.table("apps").search(where("project_id") == project_id):
        service_id = app.get("service_id")
        # stats_socket = Path(conf.RUN_DIR) / f"{service_id}-stats.sock"
        # print(read_stats(str(stats_socket)))
        # print(f"{stats_socket=} {service_id=}")
        # status = get_service_status(
        #    (Path(conf.RUN_DIR) / f"{service_id}-stats.sock")
        # )
        apps_out.append({
            "name": app.get("name"),
            # 'status': status or "uknown",
            "id": service_id,
        })
    if not apps_out:
        console.info("You have not created any apps yet.")
        console.info("Create apps using the `pikesquares apps create` command")
    else:
        console.print_response(
            apps_out,
            title=f"Apps in project '{project}'",
            show_id=show_id,
            exclude=["parent_id", "options"]
        )

@app.command(short_help="Delete existing app by name or id\nAliases:[i] delete, rm")
@app.command()
def delete(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Option("--name", "-n", help="Name of app to delete")] = "",
):
    """
    Delete existing app by name or id

    Aliases:[i] delete, rm
    """
    obj = ctx.ensure_object(dict)
    #device_handler = obj.get("device-handler")
    custom_style = obj.get("cli-style")

    db = services.get(obj, TinyDB)
    device_handler = services.get(obj, device.DeviceService)

    selected_app_cuid = None
    if not app_name:
        #with TinyDB(device_handler.svc_model.device_db_path) as db:
        apps_db = db.table("apps")
        apps_all = apps_db.all()
        if not len(apps_all):
            console.info("no apps available.")
            raise typer.Exit()

        apps_choices = []
        for app in apps_all:
            apps_choices.append(
                questionary.Choice(
                    f"{app.get('name')} [{app.get('service_id')}",
                    value=app.get("service_id"),
                )
            )
        prompt_apps_to_delete = questionary.checkbox(
            "Select the app(s) to be deleted?",
            choices=apps_choices,
            style=custom_style,
        )
        for selected_app_cuid in prompt_apps_to_delete.ask() or []:
            console.info(f"selected app to delete: {selected_app_cuid=}")

            # rm app configs
            app = apps_db.get(Query().service_id == selected_app_cuid)
            project_id = app.get("project_id")
            selected_app_config_path = device_handler.svc_model.config_dir / \
                f"{project_id}" / "apps" \
                / f"{selected_app_cuid}.json"

            if selected_app_config_path.exists():
                selected_app_config_path.unlink(missing_ok=True)
                console.info(f"deleted app config @ {selected_app_cuid}")
            else:
                console.info(f"{str(selected_app_config_path)} does not exist")

            apps_db.remove(where("service_id") == selected_app_cuid)
            console.success(f"Removed app [{selected_app_cuid}]")

if __name__ == "__main__":
    app()
