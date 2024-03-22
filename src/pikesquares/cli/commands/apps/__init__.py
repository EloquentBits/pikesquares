import os
import sys
import subprocess
from pathlib import Path
from enum import Enum
from typing import Tuple

import typer
import questionary
import giturlparse

from .validators import (
    RepoAddressValidator, 
    PathValidator,
    #NameValidator,
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
            #"--quiet",
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

def prompt_repo_url(custom_style:questionary.Style) -> Path:
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

def gather_repo_details(custom_style:questionary.Style) -> Tuple[str, str, Path]:
    repo_url = prompt_repo_url(custom_style)
    giturl:giturlparse.result.GitUrlParsed = giturlparse.parse(repo_url)
    repo_name: str = giturl.name

    base_dir: Path = prompt_base_dir(repo_name, custom_style)
    clone_into_dir: Path = Path(base_dir) / repo_name
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
            base_dir: Path = prompt_base_dir(repo_name, custom_style)
        elif len(clone_into_dir_files):
            if not questionary.confirm(
                f"Directory {str(clone_into_dir)} is not emptry. Continue?",
                default=True,
                auto_enter=True,
                style=custom_style,
            ).ask():
                raise typer.Exit()
    return repo_url, repo_name, clone_into_dir
