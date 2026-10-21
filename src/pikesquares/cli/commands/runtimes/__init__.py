from pathlib import Path

import pluggy
import questionary
import structlog_sentry_logger
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

logger = structlog_sentry_logger.get_logger()


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
            if (
                python_version.implementation == runtime_name
                and python_version.variant == "default"
                and not python_version.symlink
            ):
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
            console.info(f"provisioning runtime {runtime_name} {runtime_version.version}")
            runtime = provision_python_app_runtime(runtime_version, uow)
            if runtime:
                console.success(f":heavy_check_mark:     Provisioned {runtime_name} {runtime_version.version} runtime")

                console.info(f"installing runtime {runtime_name} {runtime_version.version}")
                PythonAppRuntime.install(runtime_version)
                console.success(f":heavy_check_mark:     Installed {runtime_name} {runtime_version.version} runtime")

            else:
                console.warning(f"Unable to provision {runtime_name} {runtime_version.version}")

            scie_home = conf.data_dir / Path("scie-pikesquares")

            if not (conf.plugins_dir / f"{runtime_version.uwsgi_plugin_name}_plugin.so").exists():
                # FIXME find out where the interpreter is
                # using interpreter @ {runtime_version.path}
                console.info("building uWSGI Python plugin")
                plugin_path = PythonAppRuntime.build_uwsgi_python_plugin(
                    runtime_version, conf.plugins_dir, scie_home, uv_bin=conf.UV_BIN
                )
                if plugin_path:
                    console.success(f"uWSGI Python plugin built and available at {plugin_path}.")
                else:
                    console.warning("unable to build uWSGI Python plugin.")
            else:
                logger.info(f"skip building {runtime_version.uwsgi_plugin_name}_plugin.so. One already exists.")

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
            if not python_version.symlink:
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
            delete_python_app_runtime(runtime_version, uow)
            PythonAppRuntime.uninstall(runtime_version, conf.plugins_dir)
            # console.warning(f"unable to provision {runtime_name} {runtime_version}")
            uow.commit()
            console.success(f":heavy_check_mark:     Removed {runtime_name} {runtime_version.version} runtime")
        except Exception as exc:
            logger.exception(exc)
            # console.print(traceback.format_exc())
            console.warning(f"Unable to remove runtime {runtime_name}")
            uow.rollback()
            raise typer.Exit(1) from None
