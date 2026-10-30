# import os
# import sys
# import sysconfig
import tempfile
import traceback
from pathlib import Path
from typing import Annotated

import questionary
import structlog_sentry_logger
import typer

# from packaging.version import Version
from pikesquares import services
from pikesquares.cli.console import console
from pikesquares.conf import AppConfig
from pikesquares.domain.python_runtime import PythonAppRuntime, PythonRuntimeVersion
from pikesquares.service_layer.handlers.runtimes import (
    provision_python_app_runtime,
)
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.service_layer.uv import PluginHeaderFileMissingError, build_plugin, build_uwsgi, clone_repo

# from pikesquares.service_layer.handlers.runtimes import get_uv_python_installations

logger = structlog_sentry_logger.getLogger(__name__)


plugins = {
    "sqlite3": {
        "name": "sqlite3",
        "header-filename": "sqlite3.h",
        "error-message-hint-macos": "install python3-dev package. i.e. brew install libsqlite3-dev",
        "error-message-hint-linux": "install libsqlite3-dev package. i.e. sudo apt install libsqlite3-dev",
    },
    "emperor_zeromq": {
        "name": "emperor_zeromq",
        "header-filename": "",
        "error-message-hint-macos": "install libzmq package and development header files. i.e. brew install libsqlite3-dev",
        "error-message-hint-linux": "install libzmq  package and development header files. i.e. sudo apt install libzmq5 libzmq3-dev",
    },
}

app = typer.Typer()


@app.command(short_help="Build uWSGI.\nAliases:[u] uwsgi")
@app.command(
    # "new", hidden=True
)
def uwsgi(
    ctx: typer.Context,
):
    logger.info("building uWSGI binary")
    context = ctx.ensure_object(dict)
    conf = services.get(context, AppConfig)

    with tempfile.TemporaryDirectory() as scie_home:
        clone_repo(scie_home)
        try:
            build_uwsgi(conf, scie_home)
        except SCIERepoDoesNotExistError:
            logger.error("unable to clone scie-pikesquares repo")

        except UWSGISourceFilesMissingError:
            logger.error("unable to build plugin. uWSGI source files missing")


@app.command(short_help="Build uWSGI Python plugin.\nAliases:[p] python-plugin")
@app.command(
    # "new", hidden=True
)
def python_plugin(
    ctx: typer.Context,
    version: Annotated[
        str | None, typer.Option(help="Python interpreter version to build the uWSGI plugin with")
    ] = None,
    implementation: Annotated[
        str | None, typer.Option(help="Python implementation to build the uWSGI plugin with")
    ] = None,
    py_bin: Annotated[str | None, typer.Option(help="Python executable path to build the uWSGI plugin with")] = None,
):
    """
    # do this only before building the Python plugin
    if not (include_dir / "Python.h").exists():
        inc = sysconfig.get_path("include")
        console.warning("Python development header files are not installed.")
        console.warning(f"Checked path: {os.path.join(inc, 'Python.h') if inc else 'N/A'}")
        if platform == "linux":
            console.info("install python3-dev package. i.e. sudo apt install python3-dev")
        elif platform == "macos":
            console.info("install python3-dev package. i.e. brew install python3-dev")
        raise typer.Exit(1)
    """

    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    conf = services.get(context, AppConfig)
    uow = services.get(context, UnitOfWork)
    logger.info("build python plugin cli")

    if not py_bin:
        python_versions = [
            ver for ver in PythonAppRuntime.list_all_versions(conf.UV_BIN) if ver.implementation in ["cpython", "pypy"]
        ]
        choices = []
        for python_version in python_versions:
            title = f"{implementation} {python_version.version}"
            if python_version.path:
                title += f" installed @ {python_version.path}"
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
                f"calling provision_python_app_runtime: {runtime_version.version} {runtime_version.implementation}"
            )
            runtime = provision_python_app_runtime(runtime_version, uow)
            if runtime:
                console.success(
                    f":heavy_check_mark:     Provisioned {runtime_version.version} {runtime_version.implementation}"
                )
                logger.info(f"installing runtime {runtime_version.version}")
                PythonAppRuntime.install(runtime_version)
                scie_home = conf.data_dir / Path("scie-pikesquares")
                result = PythonAppRuntime.build_uwsgi_python_plugin(
                    runtime_version, conf.plugins_dir, scie_home, uv_bin=conf.UV_BIN
                )
                logger.info(result)
            else:
                console.warning(f"unable to provision {runtime_version.version} {runtime_version.implementation}")

            uow.commit()
        except Exception as exc:
            # logger.exception(exc)
            print(traceback.format_exc())
            # console.print(traceback.format_exc())
            console.warning(f"Unable to provision runtime {runtime_version.version} {runtime_version.implementation}")
            uow.rollback()
            raise typer.Exit(1) from None

    # logger.debug(f"build {py_version} python plugin - {result.returncode=}")

    #   --plugin plugins/python pikesquares.ini python312
    #   PYTHON=python3.4 ./uwsgi --build-plugin "plugins/python python34"


@app.command(short_help="Build uWSGI sqlite3 plugin.\nAliases:[p] sqlite3-plugin")
@app.command(
    # "new", hidden=True
)
def sqlite3_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = services.get(context, AppConfig)

    with tempfile.TemporaryDirectory() as scie_home:
        clone_repo(scie_home)
        try:
            build_plugin(conf, "sqlite3", scie_home)
        except PluginHeaderFileMissingError as exc:
            console.warning("sqlite3_plugin development header files are not installed.")
            console.info(exc.message)
            raise typer.Exit(1) from None


@app.command(short_help="Build uWSGI emperor-zeromq plugin.\nAliases:[p] emperor-zeromq-plugin")
@app.command(
    # "new", hidden=True
)
def emperor_zeromq_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = services.get(context, AppConfig)
    with tempfile.TemporaryDirectory() as scie_home:
        clone_repo(scie_home)
        try:
            build_plugin(conf, "emperor_zeromq", scie_home)
        except PluginHeaderFileMissingError as exc:
            console.warning("emperor_zeromq_plugin development header files are not installed.")
            console.info(exc.message)
            raise typer.Exit(1) from None


@app.command(short_help="Build uWSGI tuntap plugin.\nAliases:[p] tuntap-plugin")
@app.command(
    # "new", hidden=True
)
def tuntap_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = services.get(context, AppConfig)
    with tempfile.TemporaryDirectory() as scie_home:
        logger.info(f"tuntap plugin: {scie_home=} {scie_home=}")
        clone_repo(scie_home)
        try:
            build_plugin(conf, "tuntap", scie_home)
        except PluginHeaderFileMissingError as exc:
            console.warning("plugin development header files are not installed.")
            console.info(exc.message)
            raise typer.Exit(1) from None


@app.command(short_help="Build uWSGI pty plugin.\nAliases:[p] pty-plugin")
@app.command(
    # "new", hidden=True
)
def pty_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = services.get(context, AppConfig)
    with tempfile.TemporaryDirectory() as scie_home:
        clone_repo(scie_home)
    try:
        build_plugin(conf, "pty", scie_home)
    except PluginHeaderFileMissingError as exc:
        console.warning("plugin development header files are not installed.")
        console.info(exc.message)
        raise typer.Exit(1) from None


@app.command(short_help="Build uWSGI forkpty_router plugin.\nAliases:[p] forkpty-router-plugin")
@app.command(
    # "new", hidden=True
)
def forkpty_router_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = services.get(context, AppConfig)
    with tempfile.TemporaryDirectory() as scie_home:
        clone_repo(scie_home)
        try:
            build_plugin(conf, "forkpty_router", scie_home)
        except PluginHeaderFileMissingError as exc:
            console.warning("plugin development header files are not installed.")
            console.info(exc.message)
            raise typer.Exit(1) from None


@app.command(short_help="Build uWSGI logfile plugin.\nAliases:[p] logfile-plugin")
@app.command(
    # "new", hidden=True
)
def logfile_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = services.get(context, AppConfig)
    with tempfile.TemporaryDirectory() as scie_home:
        clone_repo(scie_home)
        try:
            build_plugin(conf, "logfile", scie_home)
        except PluginHeaderFileMissingError as exc:
            console.warning("plugin development header files are not installed.")
            console.info(exc.message)
            raise typer.Exit(1) from None
