from pathlib import Path

import pluggy
import questionary
import structlog
import typer

from pikesquares import services
from pikesquares.cli.console import console
from pikesquares.conf import AppConfig
from pikesquares.domain.python_runtime import PythonAppRuntime
from pikesquares.service_layer.handlers.runtimes import (
    delete_python_app_runtime,
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
        choices = []
        for python_version in PythonAppRuntime.list_all_versions(conf.UV_BIN):
            if python_version.implementation == runtime_name and python_version.variant == "default":
                disabled = f"installed @ {python_version.path}" if python_version.path else ""
                choices.append(questionary.Choice(python_version.version, value=python_version, disabled=disabled))

        runtime_version = questionary.select(
            "Select from available versions: ",
            choices=choices,
            style=custom_style,
        ).ask()
        if not runtime_version:
            raise typer.Exit(0)

        try:
            logger.info(
                f"calling provision_python_app_runtime: {runtime_version.version} {runtime_version.implementation}"
            )
            runtime = provision_python_app_runtime(runtime_version, uow)
            if runtime:
                console.success(f":heavy_check_mark:     Provisioned {runtime_name} {runtime_version} runtime")
                logger.info(f"installing runtime {runtime_version}")
                PythonAppRuntime.install(f"{runtime_version.implementation}{runtime_version.version}")

            else:
                console.warning(f"unable to provision {runtime_name} {runtime_version}")

            scie_home = conf.data_dir / Path("scie-pikesquares")
            result = PythonAppRuntime.build_uwsgi_python_plugin(
                runtime_version, conf.plugins_dir, scie_home, uv_bin=conf.UV_BIN
            )
            logger.info(result)

        except Exception as exc:
            logger.exception(exc)
            # console.print(traceback.format_exc())
            console.warning(f"Unable to provision runtime {runtime_name}")
            uow.rollback()
            raise typer.Exit(1) from None

    uow.commit()


@app.command(short_help="Remove runtime.\nAliases:[i] remove, rm, delete")
@app.command(
    # "new", hidden=True
)
def delete(
    ctx: typer.Context,
    # project_name: Optional[str] = typer.Argument("", help="New project name"),
):
    """
    Remove runtime

    Aliases: [i] remove, rm, delete
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

    runtime_name = questionary.select(
        "Select from available runtimes: ",
        choices=[
            questionary.Choice("CPython", value="cpython"),
            questionary.Choice("pypy", value="pypy"),
            # questionary.Separator(),
            # questionary.Choice("PHP", disabled="coming soon"),
            # questionary.Choice("Lua", disabled="coming soon"),
            # questionary.Choice("Perl", disabled="coming soon"),
        ],
        style=custom_style,
    ).ask()
    if not runtime_name:
        raise typer.Exit(0)

    if runtime_name in ["cpython", "pypy"]:
        choices = []
        for python_version in PythonAppRuntime.only_installed(conf.UV_BIN):
            title = f"{python_version.version} installed @ {python_version.path}" if python_version.path else ""
            choices.append(questionary.Choice(title, value=python_version))

        runtime_version = questionary.select(
            "Select from available versions: ",
            choices=choices,
            style=custom_style,
        ).ask()
        if not runtime_version:
            raise typer.Exit(0)

        try:
            logger.info(
                f"calling delete_python_app_runtime: {runtime_version.version} {runtime_version.implementation}"
            )
            delete_python_app_runtime(runtime_version, uow)
            logger.info(f"removing runtime {runtime_version}")
            PythonAppRuntime.uninstall(runtime_version)
            # console.warning(f"unable to provision {runtime_name} {runtime_version}")
            uow.commit()
            console.success(f":heavy_check_mark:     Removed {runtime_name} {runtime_version} runtime")
        except Exception as exc:
            logger.exception(exc)
            # console.print(traceback.format_exc())
            console.warning(f"Unable to remove runtime {runtime_name}")
            uow.rollback()
            raise typer.Exit(1) from None
