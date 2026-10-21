from pathlib import Path

import pluggy
import questionary
import structlog
import typer

from pikesquares import services
from pikesquares.cli.console import console
from pikesquares.conf import AppConfig
from pikesquares.service_layer.handlers.codebases import (
    provision_editable_codebase,
    provision_managed_codebase,
)
from pikesquares.service_layer.handlers.prompt_validators import PathValidator, RepoAddressValidator
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.get_logger()


app = typer.Typer()


def prompt_base_dir(repo_name: str, custom_style: questionary.Style) -> Path:
    return questionary.path(
        f"Choose a directory to clone your `{repo_name}` git repository into: ",
        default=str(Path.cwd()),
        only_directories=True,
        style=custom_style,
        validate=PathValidator,
    ).unsafe_ask()


@app.command(short_help="Add runtime.\nAliases:[i] new")
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
    custom_style = context.get("cli-style")
    conf = services.get(context, AppConfig)
    uow = services.get(context, UnitOfWork)
    plugin_manager = services.get(context, pluggy.PluginManager)

    device = uow.devices.get_by_machine_id(conf.machine_id)

    if not device:
        console.error(f"cli up: unable to locate device by machine id {conf.machine_id}")
        raise typer.Exit(code=0) from None

    """
        Managed: Clone from a git repo into a project data directory.
        Editable: Clone from a git repo into a local directory.
    """

    prompt_style = questionary.Style(
        [
            ("separator", "fg:#6C6C6C"),
            ("qmark", "fg:#FF9D00 bold"),
            ("question", ""),
            ("selected", "fg:#5F819D"),
            ("pointer", "fg:#FF9D00 bold"),
            ("answer", "fg:#5F819D bold"),
            ("instruction", "fg:#5F819D bold"),
            ("aaa", "#ff0066"),
        ]
    )

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
    choices = [
        questionary.Choice(
            "Managed: Clone from a git repo into a project data directory.\n             and more here",
            value="managed",
        ),
        questionary.Choice(
            "<aaa>Editable</aaa>: Clone from a git repo into a local directory.",
            value="editable",
        ),
    ]

    codebase_type = questionary.select(
        "Select from available codebase types: ",
        instruction="\n       this is instruction  \n",
        choices=choice1,
        style=prompt_style,
    ).ask()
    if not codebase_type:
        raise typer.Exit(0)

    if codebase_type == "managed":
        try:
            managed_codebase = provision_managed_codebase(uow)
            if managed_codebase:
                console.success(f":heavy_check_mark:     Provisioned {codebase_type} codebase")
                uow.commit()
            else:
                console.warning(f"unable to provision {codebase_type} codebase")

        except Exception as exc:
            logger.exception(exc)
            # console.print(traceback.format_exc())
            console.warning("Unable to provision codebasel")
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
