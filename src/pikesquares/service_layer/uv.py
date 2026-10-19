import json
import tempfile
from pathlib import Path

import structlog
from plumbum import CommandNotFound, LocalPath, ProcessExecutionError
from plumbum import local as pl_local
from plumbum.path.utils import move

from pikesquares.exceptions import (
    UvCommandExecutionError,
    UvPipInstallError,
    UvPipListError,
    UvSyncError,
)

logger = structlog.getLogger()


class SCIERepoDoesNotExistError(Exception):
    pass


class UWSGISourceFilesMissingError(Exception):
    pass


class PluginHeaderFileMissingError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


"""

    uv = pl_local[str(conf.UV_BIN)]
    try:
        result = uv.run(cmd_args, cwd=str(cwd), **{"env": cmd_env})
    except ProcessExecutionError as exc:
        for line in exc.stdout.split("\n"):
            print(line)

        if exc.stderr:
            logger.debug(f"building {name} plugin -  errors:")
            for line in exc.stderr.split("\n"):
                print(line)

"""


def which_uv() -> LocalPath:

    try:
        return pl_local.which("uv")
    except CommandNotFound:
        logger.error("unable to locate uv command.")


def clone_repo(scie_home):

    repo_url = "https://github.com/EloquentBits/scie-pikesquares.git"
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


def build_uwsgi_deps(conf):

    with tempfile.TemporaryDirectory() as scie_home:
        clone_repo(scie_home)
        try:
            build_uwsgi(conf, scie_home)
        except SCIERepoDoesNotExistError:
            logger.error("unable to clone scie-pikesquares repo")
            return

        except UWSGISourceFilesMissingError:
            logger.error("unable to build plugin. uWSGI source files missing")
            return

        for plugin in conf.required_plugins:
            plugin_path = conf.plugins_dir / f"{plugin}_plugin.so"
            if not plugin_path.exists():
                try:
                    build_plugin(conf, plugin, scie_home)
                except PluginHeaderFileMissingError as exc:
                    logger.warning(f"{plugin} development header files are not installed.")
                    logger.info(exc.message)
                    return

                except UWSGISourceFilesMissingError:
                    logger.error("unable to build plugin. uWSGI source files missing")
                    return


def build_python_plugin(
    py_bin: LocalPath | Path,
    scie_home: LocalPath | Path | None = None,
    uv_bin: LocalPath | Path | None = None,
):
    # uv run uwsgiconfig.py --plugin plugins/python
    uv_bin = uv_bin or which_uv()
    cmd_env = {"PYTHON": str(py_bin)}
    cmd_args = ["run", "uwsgiconfig.py", "--plugin", "plugins/python"]
    if cmd_env:
        pl_local.env.update(cmd_env)
        logger.debug(f"{cmd_env=}")

    # with pl_local.as_user(run_as_user):
    uv = pl_local[str(uv_bin)]

    try:
        result = uv.run(cmd_args, cwd=str(scie_home / "uwsgi"), **{"env": cmd_env})
        logger.info(result)
        return result
    except ProcessExecutionError as exc:
        for line in exc.stdout.split("\n"):
            print(line)

        if exc.stderr:
            for line in exc.stderr.split("\n"):
                print(line)


def build_plugin(conf, name, scie_home):
    """
    include_dir = Path(sysconfig.get_path("include"))
    if name in plugins:
        platform = None
        if sys.platform == "darwin":
            platform = "macos"
        elif sys.platform.startswith("linux"):
            platform = "linux"

        # print(f"{include_dir / plugins[name]['header-filename']}")
        # if not (include_dir / plugins[name]["header-filename"]).exists():
        #    raise PluginHeaderFileMissingError(plugins[name]["error-message-hint-" + platform])
    """

    # scie_home = conf.data_dir / Path("scie-pikesquares")
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
    logger.info(f"Starting building the {name} uWSGI plugin")
    try:
        result = uv.run(cmd_args, cwd=str(cwd), **{"env": cmd_env})
    except ProcessExecutionError as exc:
        for line in exc.stdout.split("\n"):
            print(line)

        if exc.stderr:
            logger.debug(f"building {name} plugin -  errors:")
            for line in exc.stderr.split("\n"):
                print(line)

        return

    logger.info(f"{conf.plugins_dir=}")
    # (uwsgi_src_home / f"{name}_plugin.so").rename(conf.plugins_dir / f"{name}_plugin.so")
    pl_local.path(uwsgi_src_home).joinpath(f"{name}_plugin.so").move(conf.plugins_dir / f"{name}_plugin.so")

    if (conf.plugins_dir / f"{name}_plugin.so").exists():
        logger.info(f"Completed building the uWSGI {name} plugin.")
    else:
        logger.info(f"Failed to build the uWSGI {name} plugin.")


def build_uwsgi(conf, scie_home) -> None:
    if not Path(scie_home).exists():
        raise SCIERepoDoesNotExistError()

    uwsgi_src_home = scie_home / Path("uwsgi")
    if not pl_local.path(scie_home / Path("uwsgi")).exists():
        raise UWSGISourceFilesMissingError()

    cmd_env = {}
    cmd_args = ["run", "uwsgiconfig.py", "--build", "nolang"]
    if cmd_env:
        pl_local.env.update(cmd_env)
        logger.debug(f"{cmd_env=}")

    logger.info("Starting building the uWSGI binary")
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
        return

    # (conf.data_dir / "bin").mkdir(parents=True, exist_ok=True)
    # os.remove(str(conf.data_dir / "bin/uwsgi"))
    # pl_local.path(str(uwsgi_src_home / "uwsgi")).move(str(conf.data_dir / "bin"))
    move(uwsgi_src_home / "uwsgi", conf.data_dir / "bin")

    if pl_local.path(str(conf.data_dir / "bin/uwsgi")).exists():
        logger.info("Completed building the uWSGI binary.")
    else:
        logger.info("Failed to build the uWSGI binary.")


def install_python_version(
    version: str,
    uv_bin: LocalPath | Path | None = None,
    # cwd
):
    uv_bin = uv_bin or which_uv()
    cmd_env = {}
    cmd_args = ["python", "install", version]
    if cmd_env:
        pl_local.env.update(cmd_env)
        logger.debug(f"{cmd_env=}")
    cmd_args = list(filter(lambda x: x != "", cmd_args))
    logger.info(cmd_args)
    uv = pl_local[str(uv_bin)]
    error_msg = f"uv run {' '.join(cmd_args)}"
    try:
        result = uv.run(
            cmd_args,
            # cwd=str(cwd),
            **{"env": cmd_env},
        )
        logger.info(result)
        if result[0] == 0:
            return result[1]
        else:
            error_msg = f"uv run {' '.join(cmd_args)} error: {result[2]}"
            raise UvCommandExecutionError(error_msg)

    except ProcessExecutionError as exc:
        for line in exc.stdout.split("\n"):
            print(line)

        if exc.stderr:
            for line in exc.stderr.split("\n"):
                print(line)
        raise UvCommandExecutionError(error_msg)


def list_installed_python_versions(
    uv_bin: LocalPath | Path | None = None,
    only_installed: bool | None = False,
    only_downloads: bool | None = False,
    # cwd
):
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
    uv_bin = uv_bin or which_uv()
    cmd_env = {}
    cmd_args = [
        "python",
        "list",
        "--only-installed" if only_installed else "",
        "--only-downloads" if only_downloads else "",
        "--output-format",
        "json",
    ]
    if cmd_env:
        pl_local.env.update(cmd_env)
        logger.debug(f"{cmd_env=}")
    cmd_args = list(filter(lambda x: x != "", cmd_args))
    logger.info(cmd_args)
    uv = pl_local[str(uv_bin)]
    error_msg = f"uv run {' '.join(cmd_args)}"
    try:
        result = uv.run(
            cmd_args,
            # cwd=str(cwd),
            **{"env": cmd_env},
        )
        logger.info(result)
        if result[0] == 0:
            return json.loads(result[1])
        else:
            error_msg = f"uv run {' '.join(cmd_args)} error: {result[2]}"
            raise UvCommandExecutionError(error_msg)

    except ProcessExecutionError as exc:
        for line in exc.stdout.split("\n"):
            print(line)

        if exc.stderr:
            for line in exc.stderr.split("\n"):
                print(line)
        raise UvCommandExecutionError(error_msg)


def uv_cmd(
    uv_bin: Path,
    cmd_args: list[str],
    # run_as_user: str = "pikesquares",
    cmd_env: dict | None = None,
    chdir: Path | None = None,
) -> tuple[str, str, str]:
    # logger.info(f"{cmd_args=}")
    try:
        # with pl_local.as_user(run_as_user):
        with pl_local.cwd(chdir):
            uv = pl_local[str(uv_bin)]
            if cmd_env:
                pl_local.env.update(cmd_env)
            retcode, stdout, stderr = uv.run(cmd_args)
            # if stdout:
            #    logger.debug(stdout)
            # if stderr:
            #    logger.debug(stderr)
            return retcode, stdout, stderr
    except ProcessExecutionError as exc:
        logger.exception(exc)
        raise UvCommandExecutionError(f"uv run {' '.join(cmd_args)}")
        # print(vars(exc))
        # {
        #    'message': None,
        #    'host': None,
        #    'argv': ['/home/pk/.local/bin/uv', 'run', 'manage.py', 'check'],
        #    'retcode': 1
        #    'stdout': '',
        #    'stderr': "warning: `VIRTUAL_ENV=/home/pk/dev/eqb/pikesquares/.venv` does not match the project environment path `.venv` and will be ignored\nSystemCheckError: System check identified some issues:\n\nERRORS:\n?: (caches.E001) You must define a 'default' cache in your CACHES setting.\n\nSystem check identified 1 issue (0 silenced).\n"
        # }
        # print(traceback.format_exc())
        # raise UvCommandExecutionError(
        #        f"uv cmd [{' '.join(cmd_args)}] failed.\n{exc.stderr}"
        # )


def uv_dependencies_install(
    uv_bin: Path,
    venv: Path,
    repo_dir: Path,
    cmd_env: dict | None = None,
    debug: bool = False,
    python_bin: Path = Path("/usr/bin/python3"),
) -> None:

    logger.info(f"uv installing dependencies in venv @ {venv}")
    cmd_args = []
    if debug:
        cmd_args.append("--verbose")
    install_inspect_extensions = False
    # if "uv.lock" and "pyproject.toml" in self.top_level_file_names:
    #    logger.info("installing dependencies from uv.lock")
    assert repo_dir.exists(), f"repo dir {repo_dir} does not exist"

    uv = pl_local[str(conf.UV_BIN)]
    try:
        result = uv.run(cmd_args, cwd=str(cwd), **{"env": cmd_env})
    except ProcessExecutionError as exc:
        for line in exc.stdout.split("\n"):
            print(line)

        if exc.stderr:
            logger.debug(f"building {name} plugin -  errors:")
            for line in exc.stderr.split("\n"):
                print(line)

    try:
        retcode, stdout, stderr = uv_cmd(
            Path(uv_bin),
            [
                "sync",
                # "--directory", str(app_root_dir),
                # "--project", str(app_root_dir),
                # "--frozen",
                # "--no-sync",
                "--all-groups",
                "--all-extras",
                "--python",
                str(python_bin),
                # If the lockfile is not up-to-date,
                # an error will be raised instead of updating the lockfile.
                # "--locked",
                "--color",
                "never",
                # FIXME
                "--cache-dir",
                "/var/lib/pikesquares/uv-cache",
                *cmd_args,
            ],
            cmd_env=cmd_env,
            chdir=repo_dir,
        )
        # print(retcode)
        # print(stdout)
        # print(stderr)
    except UvCommandExecutionError:
        raise UvSyncError("`uv sync` unable to install dependencies")

    # elif not "uv.lock" in self.top_level_file_names  \
    #    and "pyproject.toml" in self.top_level_file_names:
    #    logger.info("uv install")

    if 0:  # "requirements.txt" in self.top_level_file_names:
        # uv pip install -r requirements.txt
        # uv add -r requirements.txt
        # uv export --format requirements-txt
        logger.info("installing depedencies from requirements.txt")
        cmd_args = [*cmd_args, "pip", "install", "-r", "requirements.txt"]
        try:
            retcode, stdout, stderr = uv_cmd(
                Path(uv_bin),
                cmd_args,
                cmd_env=cmd_env,
                chdir=repo_dir,
            )
        except UvCommandExecutionError:
            raise UvPipInstallError("unable to install dependencies from requirements.txt")
            # for p in Path(app_root_dir / ".venv/lib/python3.12/site-packages").iterdir():
            #    print(p)
        if install_inspect_extensions:
            logger.info("installing inspect-extensions")
            cmd_args = [*cmd_args, "pip", "install", "inspect-extensions"]
            try:
                retcode, stdout, stderr = uv_cmd(Path(uv_bin), cmd_args, cmd_env)
            except UvCommandExecutionError:
                raise UvPipInstallError("unable to install inspect-extensions in")
    # else:
    #    raise PythonRuntimeDepsInstallError("unable to install Python runtime dependencies")
    #


def uv_dependencies_list(
    uv_bin: Path,
):
    cmd_env = {}
    cmd_args = ["pip", "list", "--format", "json"]
    try:
        retcode, stdout, stderr = uv_cmd(
            Path(uv_bin),
            cmd_args,
            cmd_env,
        )
        return json.loads(stdout)
    except UvCommandExecutionError:
        raise UvPipListError("unable to get a list of dependencies")
