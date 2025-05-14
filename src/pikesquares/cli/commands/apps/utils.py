import time
import os
import traceback
import sys
import subprocess
from pathlib import Path

import typer
import git
import questionary
import giturlparse
from cuid import cuid
#from tinydb import TinyDB, where, Query
import structlog


from pikesquares.conf import AppConfig
from pikesquares.services.project import SandboxProject, Project
from pikesquares.services.router import (
    HttpRouter,
    HttpsRouter,
)

from .validators import (
    RepoAddressValidator,
    PathValidator,
)

logger = structlog.get_logger()


def detect_runtime(cwd: Path):

    py_files = [
        "main.py",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
    ]


def detect_py_version():
    """
    The version can be overridden by

    Setting the NIXPACKS_PYTHON_VERSION environment variable
    Setting the version in a .python-version file
    Setting the version in a runtime.txt file
    Setting the version in a .tool-versions file

    You also specify the exact poetry, pdm, and uv versions:

    The NIXPACKS_POETRY_VERSION environment variable or poetry in a .tool-versions file
    The NIXPACKS_PDM_VERSION environment variable
    The NIXPACKS_UV_VERSION environment variable or uv in a .tool-versions file

    """


def install_py_deps():
    """
    If requirements.txt
    pip install -r requirements.txt

    If pyproject.toml
    pip install --upgrade build setuptools && pip install .

    If pyproject.toml (w/ poetry.lock)
    poetry install --no-dev --no-interactive --no-ansi

    If pyproject.toml (w/ pdm.lock)
    pdm install --prod

    If Pipfile (w/ Pipfile.lock)
    PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

    if uv.lock:

    uv sync --no-dev --frozen

    """


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


def prompt_base_dir(repo_name: str, custom_style: questionary.Style) -> Path:
    return questionary.path(
            f"Choose a directory to clone your `{repo_name}` git repository into: ",
        default=os.getcwd(),
        only_directories=True,
        style=custom_style,
        validate=PathValidator,
    ).ask()


def prompt_repo_url(custom_style: questionary.Style) -> str:
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
            # "PikeSquares App Template",
            questionary.Separator(),
            questionary.Choice("PikeSquares App Template", disabled="coming soon"),
        ],
        style=custom_style,
        use_shortcuts=True,
        use_indicator=True,
        show_selected=False,
        # instruction="this is an instruction",
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

"""
def get_project(
        db: TinyDB,
        conf: AppConfig,
        project: str | None,
        sandbox_project: SandboxProject,
        custom_style: questionary.Style,
    ) -> Project:
    project_id = None
    project_name = None
    projects = db.table("projects").all()

    if not projects:
        sandbox_project.up(name="sandbox")
        cnt = 0
        while cnt < 5 and sandbox_project.get_service_status() != "running":
            time.sleep(3)
            cnt += 1
        if sandbox_project.get_service_status() != "running":
            console.warning("unable not start sandbox project. giving up.")
            # sandbox_project.service_config.unlink()
            # console.info(f"removed sandbox project config {sandbox_project.service_config.name}")
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
        project_id = db.table("projects").\
            get(Query().name == project_name).get("service_id")

    return Project(
            conf=conf,
            db=db,
            service_id=project_id,
            name=project_name,
    )


def get_router(
        db: TinyDB,
        conf: AppConfig,
        app_name: str,
        custom_style: questionary.Style,
        ) -> HttpRouter | HttpsRouter | None:

    def build_app_url(name: str, address: str) -> str:
        router_port = address.split(":")[-1]
        protocol = "http" if router_port.startswith("9") else "https"
        return f"{protocol}://{name}.pikesquares.dev:{router_port}"

    # def build_router_address(app_url: str) -> str:
    #    router_port = app_url.split(":")[-1]
    #    protocol = "http" if router_port.startswith("9") else "https"
    #    return f"{protocol}://0.0.0.0:{router_port}"

    def prompt_routers_q():
        app_url_choices = []
        for r in db.table("routers").all():
            app_url_choices.append(
                questionary.Choice(
                    build_app_url(app_name, r.get("address")),
                    value=r.get("address"),
                    checked=False,
                )
            )
        if not app_url_choices:
            http_router_addr = f"0.0.0.0:{str(get_first_available_port(port=9000))}"
            app_url_choices.append(
                questionary.Choice(
                    build_app_url(app_name, http_router_addr),
                    value=http_router_addr,
                    checked=False,
                )
            )
            https_router_addr = f"0.0.0.0:{str(get_first_available_port(port=8443))}"
            app_url_choices.append(
                questionary.Choice(
                    build_app_url(app_name, https_router_addr),
                    value=https_router_addr,
                    checked=False,
                )
            )
        return questionary.select(
            "Select a Virtual Host URL for your app: ",
            app_url_choices,
            instruction="",
            style=custom_style,
            )

    router_address = prompt_routers_q().ask()
    if not router_address:
        raise typer.Exit()

    router = db.table("routers").\
            get(Query().address == router_address)
    router_id = router.get("service_id") if router else f"router_{cuid()}"

    router_class = None
    if router_address.split(":")[-1].startswith("8"):
        router_class = HttpsRouter

    if router_address.split(":")[-1].startswith("9"):
        router_class = HttpRouter

    if router_class:
        return router_class(
                address=router_address,
                conf=conf,
                db=db,
                service_id=router_id,
        )

# validate=lambda text: True if len(text) > 0 else "Please enter a value"
# print(questionary.text("What's your name?",
#    validate=lambda text: len(text) > 0).ask())

"""
