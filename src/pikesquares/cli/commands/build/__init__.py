import json
import os
import sys
import sysconfig
import tempfile
from pathlib import Path
from typing import Annotated

import structlog
import typer
from packaging.version import Version
from plumbum import ProcessExecutionError
from plumbum import local as pl_local

from pikesquares import services
from pikesquares.cli.console import console
from pikesquares.conf import AppConfig

logger = structlog.getLogger(__name__)


class SCIERepoDoesNotExistError(Exception):
    pass


class UWSGISourceFilesMissingError(Exception):
    pass


class PluginHeaderFileMissingError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


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


def build_plugin(conf, name):

    include_dir = Path(sysconfig.get_path("include"))
    if name in plugins:
        platform = None
        if sys.platform == "darwin":
            platform = "macos"
        elif sys.platform.startswith("linux"):
            platform = "linux"

        print(f"{include_dir / plugins[name]['header-filename']}")

        if not (include_dir / plugins[name]["header-filename"]).exists():
            raise PluginHeaderFileMissingError(plugins[name]["error-message-hint-" + platform])

    scie_home = conf.data_dir / Path("scie-pikesquares")
    uwsgi_src_home = scie_home / Path("uwsgi")
    if not uwsgi_src_home.exists():
        raise UWSGISourceFilesMissingError()
    cwd = uwsgi_src_home

    cmd_env = {}
    cmd_args = ["run", "uwsgiconfig.py", "--plugin", f"plugins/{name}"]

    if cmd_env:
        pl_local.env.update(cmd_env)
        logger.debug(f"{cmd_env=}")

    # with pl_local.as_user(run_as_user):
    uv = pl_local[str(conf.UV_BIN)]

    console.info(f"Starting building the {name} uWSGI plugin")

    try:
        result = uv.run(cmd_args, cwd=str(cwd), **{"env": cmd_env})
    except ProcessExecutionError as exc:
        """
        Stdout:       | using profile: buildconf/default.ini
                    | detected include path: ['/usr/lib/gcc/x86_64-linux-gnu/14/include', '/usr/local/include', '/usr/include/x86_64-linux-gnu', '/usr/include']
                    | *** uWSGI building and linking plugin plugins/emperor_zeromq ***
                    | [cc -pthread] ./emperor_zeromq_plugin.so
                    | *** unable to build emperor_zeromq plugin ***
        Stderr:       | plugins/emperor_zeromq/emperor_zeromq.c:56:10: fatal error: zmq.h: No such file or directory
                    |    56 | #include <zmq.h>
                    |       |          ^~~~~~~
                    | compilation terminated.
        """
        for line in exc.stdout.split("\n"):
            print(line)

        if exc.stderr:
            logger.debug(f"building {name} plugin -  errors:")
            for line in exc.stderr.split("\n"):
                print(line)

        # if "#*** python plugin built and available in ./python_plugin.so ***" not in result.stdout:
        #    logger.error(f"unable to build the uWSIG python plugin for Python {py_version}")
        #    raise typer.Exit()

        return typer.Exit(code=1)

    # logger.debug(f"done building {name} plugin - {result.returncode=}")

    (uwsgi_src_home / f"{name}_plugin.so").rename(conf.plugins_dir / f"{name}_plugin.so")

    if conf.UWSGI_BIN.exists():
        console.info("Completed building the uWSGI binary.")
    else:
        console.info("Failed to build the uWSGI binary.")


def build_uwsgi(conf):
    repo_url = "https://github.com/EloquentBits/scie-pikesquares.git"
    # scie_home = pl_local.path(conf.data_dir / Path("scie-pikesquares"))
    with tempfile.TemporaryDirectory() as scie_home:
        # pl_local.path(scie_home).chown("pikesquares", "pikesquares", recursive=True)
        # if not (scie_home / ".git").exists():
        # repo = clone(repo_url, scie_home, recurse_submodules=True)
        # logger.info(repo)
        # git clone https://github.com/EloquentBits/scie-pikesquares /var/lib/pikesquares/scie-pikesquares --recurse-submodules --depth 1

        cmd_env = {}
        cmd_args = ["clone", repo_url, str(scie_home), "--recurse-submodules", "--depth", "1"]
        if cmd_env:
            pl_local.env.update(cmd_env)
            logger.debug(f"{cmd_env=}")
        git_cmd = pl_local["git"]
        # with pl_local.as_user("pikesquares"):
        try:
            result = git_cmd.run(cmd_args, **{"env": cmd_env})
        except ProcessExecutionError as exc:
            for line in exc.stdout.split("\n"):
                print(line)

            if exc.stderr:
                for line in exc.stderr.split("\n"):
                    print(line)
            return typer.Exit(code=1)

        # else:
        #    logger.info("scie-pikesquares directory exists. not cloning.")

        # if not scie_home.exists():
        #    raise SCIERepoDoesNotExistError()

        uwsgi_src_home = scie_home / Path("uwsgi")
        # if not uwsgi_src_home.exists():
        # if not pl_local.path(scie_home / Path("uwsgi")).exists():
        #    raise UWSGISourceFilesMissingError()
        # from plumbum.path.local import LocalPath

        # uv run uwsgiconfig.py --build nolang
        uwsgi_includes = [
            # "/usr/lib/gcc/x86_64-linux-gnu/15/include",
            # "/usr/local/include",
            # "/usr/include/x86_64-linux-gnu",
            # "/usr/include",
        ]
        cmd_env = {"UWSGI_INCLUDES": ",".join(uwsgi_includes)}
        cmd_args = ["run", "uwsgiconfig.py", "--build", "nolang"]
        if cmd_env:
            pl_local.env.update(cmd_env)
            logger.debug(f"{cmd_env=}")

        console.info("Starting building the uWSGI binary")
        # with pl_local.cwd(str(uwsgi_src_home)):
        uv = pl_local[str(conf.UV_BIN)]
        # with pl_local.as_user("pikesquares"):
        try:
            result = uv.run(cmd_args, cwd=str(uwsgi_src_home), **{"env": cmd_env})
        except ProcessExecutionError as exc:
            for line in exc.stdout.split("\n"):
                print(line)

            if exc.stderr:
                for line in exc.stderr.split("\n"):
                    print(line)
            return typer.Exit(code=1)

        (conf.data_dir / "bin").mkdir(parents=True, exist_ok=True)
        os.remove(str(conf.data_dir / "bin/uwsgi"))
        pl_local.path(str(uwsgi_src_home / "uwsgi")).move(str(conf.data_dir / "bin"))

        if pl_local.path(str(conf.data_dir / "bin/uwsgi")).exists():
            console.info("Completed building the uWSGI binary.")
        else:
            console.info("Failed to build the uWSGI binary.")


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

    try:
        build_uwsgi(conf)
    except SCIERepoDoesNotExistError:
        logger.error("unable to clone scie-pikesquares repo")

    except UWSGISourceFilesMissingError:
        logger.error("unable to build plugin. uWSGI source files missing")


def get_uv_python_installations(uv_bin, cwd):
    """
    [{'key': 'cpython-3.14.3-linux-x86_64-gnu',
      'version': '3.14.3',
      'version_parts': {'major': 3, 'minor': 14, 'patch': 3},
      'path': '/home/pk/.local/share/uv/python/cpython-3.14-linux-x86_64-gnu/bin/python3.14',
      'symlink': None,
      'url': None,
      'os': 'linux',
      'variant': 'default',
      'implementation': 'cpython',
      'arch': 'x86_64',
      'libc': 'gnu'},
    ]
    """

    # uv run uwsgiconfig.py --build nolang
    cmd_env = {}
    cmd_args = ["python", "list", "--only-installed", "--output-format", "json"]
    if cmd_env:
        pl_local.env.update(cmd_env)
        logger.debug(f"{cmd_env=}")

    # with pl_local.as_user(run_as_user):
    uv = pl_local[str(uv_bin)]

    try:
        result = uv.run(cmd_args, cwd=str(cwd), **{"env": cmd_env})
        return json.loads(result.stdout)
    except ProcessExecutionError as exc:
        for line in exc.stdout.split("\n"):
            print(line)

        if exc.stderr:
            for line in exc.stderr.split("\n"):
                print(line)

        return typer.Exit(code=1)


@app.command(short_help="Build uWSGI Python plugin.\nAliases:[p] python-plugin")
@app.command(
    # "new", hidden=True
)
def python_plugin(
    ctx: typer.Context,
    py_version: Annotated[
        str | None, typer.Option(help="Python interpreter version to build the uWSGI plugin with")
    ] = None,
):

    context = ctx.ensure_object(dict)
    conf = services.get(context, AppConfig)

    scie_home = conf.data_dir / Path("scie-pikesquares")
    uwsgi_src_home = scie_home / Path("uwsgi")
    cwd = uwsgi_src_home

    all_py_installs = get_uv_python_installations(conf.UV_BIN, cwd)

    if not py_version:
        py_install = max(all_py_installs, key=lambda item: Version(item["version"]))
    else:
        py_install = next(filter(lambda x: x["version"] == py_version, all_py_installs))
    py_version = py_install.get(py_version)
    py_bin_path = Path(py_install.get("path"))
    logger.info(f"building uWSGI Python plugin in {uwsgi_src_home}. {py_version} @ {str(py_bin_path)}")

    # uv run uwsgiconfig.py --plugin plugins/python

    cmd_env = {"PYTHON": str(py_bin_path)}
    cmd_args = ["run", "uwsgiconfig.py", "--plugin", "plugins/python"]
    if cmd_env:
        pl_local.env.update(cmd_env)
        logger.debug(f"{cmd_env=}")

    # with pl_local.as_user(run_as_user):
    uv = pl_local[str(uv_bin)]
    try:
        result = uv.run(cmd_args, cwd=str(cwd), **{"env": cmd_env})
    except ProcessExecutionError as exc:
        for line in exc.stdout.split("\n"):
            print(line)

        if exc.stderr:
            for line in exc.stderr.split("\n"):
                print(line)

        return typer.Exit(code=1)

    logger.debug(f"build {py_version} python plugin - {result.returncode=}")

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
    try:
        build_plugin(conf, "sqlite3")
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
    try:
        build_plugin(conf, "emperor_zeromq")
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
    try:
        build_plugin(conf, "tuntap")
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
    try:
        build_plugin(conf, "pty")
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
    try:
        build_plugin(conf, "forkpty_router")
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
    try:
        build_plugin(conf, "logfile")
    except PluginHeaderFileMissingError as exc:
        console.warning("plugin development header files are not installed.")
        console.info(exc.message)
        raise typer.Exit(1) from None
