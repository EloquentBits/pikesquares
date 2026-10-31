import shutil
import traceback
import uuid
from pathlib import Path

import git
import questionary as qy
import structlog
import typer

from pikesquares import services
from pikesquares.cli.console import console
from pikesquares.conf import AppConfig
from pikesquares.service_layer.handlers.codebases import (
    codebase_delete,
    provision_editable_codebase,
    provision_managed_codebase,
)
from pikesquares.service_layer.handlers.prompt_validators import PathValidator, RepoAddressValidator
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.get_logger()


app = typer.Typer()


def prompt_base_dir(repo_name: str, custom_style: qy.Style) -> Path:
    return qy.path(
        f"Choose a directory to clone your `{repo_name}` git repository into: ",
        default=str(Path.cwd()),
        only_directories=True,
        style=custom_style,
        validate=PathValidator,
    ).unsafe_ask()


def prompt_repo_url(custom_style: qy.Style) -> str:
    repo_url_q = qy.text(
        "Enter your app git repository url:",
        default="",
        instruction="""\nExamples:\n    https://host.xz/path/to/repo.git\n    ssh://host.xz/path/to/repo.git\n>>>""",
        style=custom_style,
        validate=RepoAddressValidator,
    )
    if not repo_url_q:
        raise typer.Exit(0) from None
    return repo_url_q.unsafe_ask()


class CloneProgress(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=""):
        # console.info(f"{op_code=} {cur_count=} {max_count=} {message=}")
        if message:
            console.info(f"Completed git clone {message}")


def try_again_q(instruction, custom_style):
    return qy.confirm(
        "Try entring a different repository url?",
        instruction=instruction,
        default=True,
        auto_enter=True,
        style=custom_style,
    )


def gather_repo_details_and_clone(
    # app_name: str,
    # app_root_dir: Path | None,
    clone_into_dir: Path,
    custom_style: qy.Style | None,
    repo_git_url: str | None = None,
) -> tuple[Path, str]:
    repo = None

    """
    prompt for repo git url
    prompt for app root dir
    compose clone into dir
    """
    repo_url = repo_git_url or prompt_repo_url(custom_style)
    # app_root_dir = app_root_dir or prompt_base_dir(app_name, custom_style)
    # clone_into_dir = Path(app_root_dir) / app_name
    if clone_into_dir.exists():
        # and any(clone_into_dir.glob("*")):
        # import ipdb;ipdb.set_trace()
        clone_into_dir_files = [path for path in clone_into_dir.glob("**/*")]
        # clone_into_dir.glob("*")
        if clone_into_dir / ".git" in clone_into_dir_files:
            # if qy.confirm(
            #    f"There appears to be a git repository already cloned in {clone_into_dir}. Overwrite?",
            #    default=False,
            #    auto_enter=False,
            #    style=custom_style,
            # ).unsafe_ask():
            shutil.rmtree(clone_into_dir)
            logger.info(f"deleted repo dir {clone_into_dir}")
        """
        elif len(clone_into_dir_files):
            if not qy.confirm(
                f"Directory {str(clone_into_dir)} is not emptry. Continue?",
                default=True,
                auto_enter=True,
                style=custom_style,
            ).unsafe_ask():
                raise typer.Exit(0) from None
        """
    # with console.status(f"cloning `{repo_name}` repository into `{clone_into_dir}`", spinner="earth"):
    try:
        while not repo:
            try:
                repo = git.Repo.clone_from(
                    repo_url,
                    clone_into_dir,
                    progress=CloneProgress(),
                    depth=1,
                    # branch="master"
                )
            except git.GitCommandError as exc:
                if "already exists and is not an empty directory" in exc.stderr:
                    if qy.confirm(
                        "Continue with this directory?",
                        instruction=f"A git repository exists at {clone_into_dir}",
                        default=True,
                        auto_enter=True,
                        style=custom_style,
                    ).unsafe_ask():
                        break
                    # base_dir = prompt_base_dir(repo_name, custom_style)
                elif "Repository not found" in exc.stderr:
                    if try_again_q(
                        f"Unable to locate a git repository at {repo_url}",
                        custom_style,
                    ).unsafe_ask():
                        gather_repo_details_and_clone(
                            app_root_dir,
                            custom_style,
                            repo_git_url,
                        )
                    raise typer.Exit(0) from None
                else:
                    console.warning(traceback.format_exc())
                    console.warning(f"{exc.stdout}")
                    console.warning(f"{exc.stderr}")
                    if try_again_q(
                        f"Unable to clone the provided repository url at {repo_url} into {clone_into_dir}",
                        custom_style,
                    ).unsafe_ask():
                        gather_repo_details_and_clone(app_root_dir, repo_git_url, custom_style)
    except Exception as exc:
        logger.info(f"failed provisioning App Codebase @ {app_root_dir}")
        logger.exception(exc)
        print(traceback.format_exc())
        raise exc
    return Path(clone_into_dir), repo_url


@app.command(short_help="Add codebase.\nAliases:[i] new")
@app.command(
    # "new", hidden=True
)
def add(
    ctx: typer.Context,
    # project_name: Optional[str] = typer.Argument("", help="New project name"),
):
    """
    Add runtime

    Aliases: [i] add, create, new
    """
    context = ctx.ensure_object(dict)
    custom_style: qy.Style | None = context.get("cli-style")
    conf = services.get(context, AppConfig)
    uow = services.get(context, UnitOfWork)

    """
        Managed: Clone from a git repo into a project data directory.
        Editable: Clone from a git repo into a local directory.
    """

    prompt_style = qy.Style(
        [
            ("separator", "fg:#6C6C6C"),
            ("qmark", "fg:#FF9D00 bold"),
            ("question", ""),
            ("selected", "fg:#5F819D"),
            ("pointer", "fg:#FF9D00 bold"),
            ("answer", "fg:#5F819D bold"),
            ("instruction", "fg:#5F819D bold"),
            ("managed", "yellow"),
            # ("managed", "#ff0066"),
            ("highlighted1", "ansigreen"),  # style for a token which should appear highlighted
            ("highlighted2", "green"),  # style for a token which should appear highlighted
        ]
    )

    """
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.shortcuts import choice
    from prompt_toolkit.styles import Style

    style = Style.from_dict(
        {
            "input-selection": "fg:#ff0000",
            "number": "fg:#884444 bold",
            "selected-option": "underline",
        }
    )
    choice1 = choice(
        message=HTML("<u>Please select a dish</u>:"),
        options=[
            ("pizza", "Pizza with mushrooms"),
            (
                "salad",
                HTML("<ansigreen>Salad</ansigreen> with <ansired>tomatoes</ansired>"),
            ),
            ("sushi", "Sushi"),
        ],
        style=style,
    )
    """

    # choices = [qy.Choice(title=[("class:text", "order a "), ("class:highlighted", "big pizza")])]
    choices = [
        qy.Choice(
            title=[
                ("class:managed", "Managed:"),
                (
                    "class:highlighted1",
                    " Clone from a git repo into a project data directory.\n             and more here",
                ),
            ],
            value="managed",
        ),
        qy.Choice(
            title=[
                ("class:managed", "Editable:"),
                ("class:highlighted2", " Clone from a git repo into a local directory."),
            ],
            value="editable",
        ),
    ]

    codebase_type = qy.select(
        "Select from available codebase types: ",
        instruction="\n       this is instruction  \n",
        choices=choices,
        style=prompt_style,
    ).ask()
    if not codebase_type:
        raise typer.Exit(0)

    if codebase_type == "managed":
        try:
            codebase_id = str(uuid.uuid4())
            clone_into_dir = conf.data_dir / "codebases" / codebase_id
            clone_into_dir.mkdir(parents=True, exist_ok=True)

            managed_codebase = provision_managed_codebase(
                codebase_id,
                clone_into_dir,
                uow,
            )
            uow.commit()
            # if managed_codebase:
            #    console.success(f":heavy_check_mark:     Provisioned {codebase_type} codebase")
            # else:
            #    console.warning(f"unable to provision {codebase_type} codebase")

            clone_into_dir, repo_git_url = gather_repo_details_and_clone(
                clone_into_dir,
                custom_style,
            )
            if repo_git_url:
                console.success(f":heavy_check_mark:     Cloned {repo_git_url} into {clone_into_dir}")
                uow.commit()
            else:
                console.warning("unable to clone codebase")

            managed_codebase.repo_git_url = repo_git_url
            managed_codebase = uow.python_app_codebases.update(managed_codebase)
            uow.commit()

        except Exception as exc:
            logger.exception(exc)
            # console.print(traceback.format_exc())
            console.error("Unable to provision codebase")
            uow.rollback()
            raise typer.Exit(1) from None

    if codebase_type == "editable":
        try:
            editable_codebase = provision_editable_codebase(uow)
            if editable_codebase:
                console.success(f":heavy_check_mark:     Provisioned {codebase_type} codebase")
            else:
                console.warning(f"unable to provision {codebase_type} codebase")

        except Exception as exc:
            logger.exception(exc)
            # console.print(traceback.format_exc())
            console.warning(f"Unable to provision {codebase_type} codebasel")
            uow.rollback()
            raise typer.Exit(1) from None


@app.command(
    "codebases",
    rich_help_panel="Show",
    short_help="Show all codebases.\nAliases:[i] codebases, codebases list",
)
# @app.command("proj", rich_help_panel="Show", hidden=True)
@app.command("list")
def list_(ctx: typer.Context, show_id: bool = False):
    """
    Show all codebases on current device

    Aliases:[i] codebases, codebases list
    """
    context = ctx.ensure_object(dict)
    conf = services.get(context, AppConfig)
    uow = services.get(context, UnitOfWork)

    device = uow.devices.get_by_machine_id(conf.machine_id)
    if not device:
        console.warning("unable to lookup device")
        raise typer.Exit(0)

    if not len(device.projects):
        console.success("Appears there have been no projects created yet.")
        raise typer.Exit(0)

    # device_zmq_monitor = uow.zmq_monitors.get_by_device_id(device.id)
    # zmq_monitor = uow.zmq_monitors.get_by_project_id(project.id)

    codebases = uow.python_app_codebases.list()
    if not len(codebases):
        console.warning("No codebases were initialized, nothing to show!")
        raise typer.Exit()

    def dir_contains_repo(clone_into_dir: Path):
        return clone_into_dir / ".git" in clone_into_dir.glob("**/*")

    codebases_out = []
    for codebase in codebases:
        codebases_out.append(
            {
                # "id": codebase.id,
                "root dir": codebase.root_dir,
                "repo_url": codebase.repo_git_url,
                "repo cloned?": True if dir_contains_repo(Path(codebase.root_dir)) else False,
            }
        )

    console.print_response(codebases_out, title=f"Codebases count: {len(codebases)}", show_id=show_id)


@app.command(short_help="Delete existing codebase(s) \nAliases:[i] delete, rm")
@app.command("rm", hidden=True)
def delete(
    ctx: typer.Context,
    # project_name: Optional[str] = typer.Argument("", help="Name of project to remove"),
):
    """
    Delete existing codebase

    Aliases:[i] delete, rm
    """
    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    uow = services.get(context, UnitOfWork)

    codebases = uow.python_app_codebases.list()
    if not len(codebases):
        console.warning("No codebases were initialized, nothing to show!")
        raise typer.Exit()

    try:
        selected_codebases = qy.checkbox(
            "Existing codebases: ",
            choices=[
                qy.Choice(
                    f"{codebase.root_dir} [{codebase.id}]",
                    value=codebase,
                    checked=False,
                )
                for codebase in codebases
            ],
            style=custom_style,
        ).unsafe_ask()
    except KeyboardInterrupt:
        console.info("selection cancelled.")
        raise typer.Exit(0) from None

    for codebase in selected_codebases:
        try:
            # TODO
            # delete directories
            codebase_delete(codebase, uow)
            uow.commit()
        except Exception as exc:
            logger.exception(exc)
            console.error(f"Unable to delete codebase {codebase.root_dir}")
            uow.rollback()
            continue
