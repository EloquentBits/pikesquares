import traceback

import pluggy
import questionary
import structlog
import typer

from pikesquares import services
from pikesquares.cli.console import console
from pikesquares.conf import AppConfig
from pikesquares.domain.python_runtime import PythonAppRuntime
from pikesquares.service_layer.handlers.runtimes import (
    provision_python_app_runtime,
)
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.get_logger()


app = typer.Typer()


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

    # answers = questionary.form(
    #    first = questionary.confirm("Would you like the next question?", default=True),
    #    second = questionary.select("Select item", choices=["item1", "item2", "item3"])
    # ).ask()

    runtime_name = questionary.select(
        "Select from available runtimes: ",
        choices=[
            questionary.Choice("CPython", value="cpython"),
            questionary.Choice("pypy", value="pypy"),
            questionary.Separator(),
            questionary.Choice("PHP", disabled="coming soon"),
            questionary.Choice("Lua", disabled="coming soon"),
            questionary.Choice("Perl", disabled="coming soon"),
        ],
        style=custom_style,
    ).ask()
    if not runtime_name:
        raise typer.Exit(0)

    if runtime_name in ["cpython", "pypy"]:
        python_versions = [
            (ver["version"], ver["path"], ver["implementation"])
            for ver in PythonAppRuntime.list_all_versions(conf.UV_BIN)
        ]
        runtime_version = questionary.select(
            "Select from available versions: ",
            choices=[
                questionary.Choice(ver, value=(ver, path, implementation), disabled=f"installed {path}" if path else "")
                for ver, path, implementation in python_versions
                if implementation == runtime_name
            ],
            style=custom_style,
        ).ask()
        if not runtime_version:
            raise typer.Exit(0)

        try:
            logger.info(f"calling provision_python_app_runtime: {runtime_version}")
            runtime = provision_python_app_runtime(runtime_version, uow)
            if runtime:
                console.success(f":heavy_check_mark:     Provisioned {runtime_name} {runtime_version} runtime")
                logger.info(f"installing runtime {runtime_version}")
                PythonAppRuntime.install(f"{runtime_version[2]}{runtime_version[0]}")

            else:
                console.warning(f"unable to provision {runtime_name} {runtime_version}")

        except Exception as exc:
            logger.exception(exc)
            # console.print(traceback.format_exc())
            console.warning(f"Unable to provision runtime {runtime_name}")
            uow.rollback()
            raise typer.Exit(1) from None

    uow.commit()
