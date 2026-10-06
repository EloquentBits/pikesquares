import json
from pathlib import Path
from typing import Annotated

import git
import structlog
import typer
from aiopath import AsyncPath
from packaging.version import Version
from plumbum import ProcessExecutionError
from plumbum import async_local as pl_local

from pikesquares import services
from pikesquares.cli.cli import run_async
from pikesquares.cli.console import console
from pikesquares.conf import AppConfig

logger = structlog.getLogger(__name__)


async def build_plugin(conf, name):

    scie_home = conf.data_dir / AsyncPath("scie-pikesquares")
    uwsgi_src_home = scie_home / AsyncPath("uwsgi")
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
        result = await uv.run(cmd_args, cwd=str(cwd), **{"env": cmd_env})
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

    if await conf.UWSGI_BIN.exists():
        console.info("Completed building the uWSGI binary.")
    else:
        console.info("Failed to build the uWSGI binary.")


async def build_uwsgi(conf):
    repo_url = "https://github.com/EloquentBits/scie-pikesquares.git"
    scie_home = conf.data_dir / AsyncPath("scie-pikesquares")
    scie_home.mkdir(parents=True, exist_ok=True)
    if not (scie_home / ".git").exists():
        repo = clone(repo_url, scie_home, recurse_submodules=True)
        logger.info(repo)
    else:
        logger.info("scie-pikesquares directory exists. not cloning.")

    uwsgi_src_home = scie_home / AsyncPath("uwsgi")

    # uv run uwsgiconfig.py --build nolang
    cmd_env = {}
    cmd_args = ["run", "uwsgiconfig.py", "--build", "nolang"]
    if cmd_env:
        pl_local.env.update(cmd_env)
        logger.debug(f"{cmd_env=}")

    # with pl_local.as_user(run_as_user):
    console.info("Starting building the uWSGI binary")
    # async with pl_local.cwd(str(uwsgi_src_home)):
    uv = pl_local[str(conf.UV_BIN)]
    try:
        result = await uv.run(cmd_args, cwd=str(uwsgi_src_home), **{"env": cmd_env})
    except ProcessExecutionError as exc:
        for line in exc.stdout.split("\n"):
            print(line)

        if exc.stderr:
            for line in exc.stderr.split("\n"):
                print(line)
        return typer.Exit(code=1)

    (uwsgi_src_home / "uwsgi").rename(conf.UWSGI_BIN)

    if await conf.UWSGI_BIN.exists():
        console.info("Completed building the uWSGI binary.")
    else:
        console.info("Failed to build the uWSGI binary.")


class CloneProgress(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=""):
        # console.info(f"{op_code=} {cur_count=} {max_count=} {message=}")
        if message:
            console.info(f"Completed git clone {message}")


def clone(repo_url, clone_into_dir: Path, recurse_submodules=False) -> Path:

    try:
        repo = git.Repo.clone_from(
            repo_url,
            clone_into_dir,
            recurse_submodules=recurse_submodules,
            depth=1,
            # progress=CloneProgress()
        )
        return repo
    except git.GitCommandError as exc:
        pass


app = typer.Typer()


@app.command(short_help="Build uWSGI.\nAliases:[u] uwsgi")
@app.command(
    # "new", hidden=True
)
@run_async
async def uwsgi(
    ctx: typer.Context,
):
    logger.info("building uWSGI binary")
    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)
    await build_uwsgi(conf)


async def get_uv_python_installations(uv_bin, cwd):
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
        result = await uv.run(cmd_args, cwd=str(cwd), **{"env": cmd_env})
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
@run_async
async def python_plugin(
    ctx: typer.Context,
    py_version: Annotated[
        str | None, typer.Option(help="Python interpreter version to build the uWSGI plugin with")
    ] = None,
):

    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)

    scie_home = conf.data_dir / AsyncPath("scie-pikesquares")
    uwsgi_src_home = scie_home / AsyncPath("uwsgi")
    cwd = uwsgi_src_home

    all_py_installs = await get_uv_python_installations(conf.UV_BIN, cwd)

    if not py_version:
        py_install = max(all_py_installs, key=lambda item: Version(item["version"]))
    else:
        py_install = next(filter(lambda x: x["version"] == py_version, all_py_installs))
    py_version = py_install.get(py_version)
    py_bin_path = AsyncPath(py_install.get("path"))
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
        result = await uv.run(cmd_args, cwd=str(cwd), **{"env": cmd_env})
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
@run_async
async def sqlite3_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)
    await build_plugin(conf, "sqlite3")


@app.command(short_help="Build uWSGI emperor-zeromq plugin.\nAliases:[p] emperor-zeromq-plugin")
@app.command(
    # "new", hidden=True
)
@run_async
async def emperor_zeromq_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)
    await build_plugin(conf, "emperor_zeromq")


@app.command(short_help="Build uWSGI tuntap plugin.\nAliases:[p] tuntap-plugin")
@app.command(
    # "new", hidden=True
)
@run_async
async def tuntap_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)
    await build_plugin(conf, "tuntap")


@app.command(short_help="Build uWSGI pty plugin.\nAliases:[p] pty-plugin")
@app.command(
    # "new", hidden=True
)
@run_async
async def pty_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)
    await build_plugin(conf, "pty")


@app.command(short_help="Build uWSGI forkpty_router plugin.\nAliases:[p] forkpty-router-plugin")
@app.command(
    # "new", hidden=True
)
@run_async
async def forkpty_router_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)
    await build_plugin(conf, "forkpty_router")


@app.command(short_help="Build uWSGI logfile plugin.\nAliases:[p] logfile-plugin")
@app.command(
    # "new", hidden=True
)
@run_async
async def logfile_plugin(
    ctx: typer.Context,
):
    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)
    await build_plugin(conf, "logfile")
