import json
from pathlib import Path

# import toml
from plumbum import local as pl_local
from plumbum import ProcessExecutionError
import structlog

from pikesquares.cli.console import console

from .exceptions import (
    UvCommandExecutionError,
    PythonRuntimeDepsInstallError,

    UvSyncError,
    UvPipInstallError,
    UvPipListError,
)


logger = structlog.get_logger()


class UVMixin:

    def create_venv(
        self,
        venv: Path,
        cmd_env: dict | None = None,
        ) -> None:
        logger.info("Creating Python virtual environment")
        logger.debug(f"`uv venv`: {str(venv)}")

        # os.chdir(app_root_dir)
        cmd_args = []

        try:
            retcode, stdout, stderr = self.uv_cmd(
                [
                  *cmd_args,
                 "venv",
                 "--verbose",
                 "--cache-dir",
                 # FIXME
                 "/var/lib/pikesquares/uv-cache",
                 # "--project",
                 # str(app_root_dir),
                 str(venv),
                ],
                cmd_env=cmd_env,
            )
        except UvCommandExecutionError:
            raise UvSyncError(f"`uv venv` unable to create venv in {str(self.venv)}")

    def run_app_init_command(
        self,
        cmd_args: list[str],
        cmd_env: dict | None = None
        ) -> tuple[str, str, str]:

        logger.info(f"failed: uv run {' '.join(cmd_args)}")
        try:
            retcode, stdout, stderr = self.uv_cmd([
                    "run",
                    "--verbose",
                    "--python",
                    "/usr/bin/python3",
                    "--color", "never",
                    *cmd_args,
                ],
                cmd_env=cmd_env,
                chdir=self.app_repo_dir,
            )
            return retcode, stdout, stderr
        except ProcessExecutionError as exc:
            logger.exception(exc)
            raise UvCommandExecutionError(f"uv run {' '.join(cmd_args)}")

    def install_dependencies(
        self,
        cmd_env: dict | None = None,
        venv: Path | None = None,
        app_tmp_dir: Path | None = None,
        ) -> None:

        logger.info(f"uv installing dependencies in venv @ {str(venv)}")
        cmd_args = []
        install_inspect_extensions = False

        # with open(self.app_root_dir / "pyproject.toml", "r") as f:
        #    config = toml.load(f)
        #    deps = config["project"]["dependencies"]
        #    print("[pikesquares] located deps in pyproject.toml")
        #    print(deps)

        #if "uv.lock" and "pyproject.toml" in self.top_level_file_names:
        #    logger.info("installing dependencies from uv.lock")
        try:
            retcode, stdout, stderr = self.uv_cmd([
                    "sync",
                    # "--directory", str(app_root_dir),
                    # "--project", str(app_root_dir),
                    # "--frozen",
                    # "--no-sync",
                    "--all-groups", "--all-extras",
                    "--verbose",
                    "--python",
                    "/usr/bin/python3",
                    # If the lockfile is not up-to-date,
                    # an error will be raised instead of updating the lockfile.
                    #"--locked",
                    "--color", "never",
                    # FIXME
                    "--cache-dir", "/var/lib/pikesquares/uv-cache",
                    *cmd_args,
                ],
                cmd_env=cmd_env,
                chdir=app_tmp_dir or self.app_repo_dir,
            )
        except UvCommandExecutionError:
            raise UvSyncError("`uv sync` unable to install dependencies")

        #elif not "uv.lock" in self.top_level_file_names  \
        #    and "pyproject.toml" in self.top_level_file_names:
        #    logger.info("uv install")

        if 0: #"requirements.txt" in self.top_level_file_names:
            # uv pip install -r requirements.txt
            # uv add -r requirements.txt
            # uv export --format requirements-txt
            logger.info("installing depedencies from requirements.txt")
            cmd_args = [*cmd_args, "pip", "install", "-r", "requirements.txt"]
            try:
                retcode, stdout, stderr = self.uv_cmd(
                    cmd_args,
                    cmd_env=cmd_env,
                    chdir=app_tmp_dir or self.app_repo_dir,
                )
            except UvCommandExecutionError:
                raise UvPipInstallError(
                    "unable to install dependencies from requirements.txt"
                )
                # for p in Path(app_root_dir / ".venv/lib/python3.12/site-packages").iterdir():
                #    print(p)
            if install_inspect_extensions:
                logger.info("installing inspect-extensions")
                cmd_args = [*cmd_args, "pip", "install", "inspect-extensions"]
                try:
                    retcode, stdout, stderr = self.uv_cmd(cmd_args, cmd_env)
                except UvCommandExecutionError:
                    raise UvPipInstallError("unable to install inspect-extensions in")
        #else:
        #    raise PythonRuntimeDepsInstallError("unable to install Python runtime dependencies")

    def dependencies_list(self):
        cmd_env = {}
        cmd_args = ["pip", "list", "--format", "json"]
        try:
            retcode, stdout, stderr = self.uv_cmd(
                    cmd_args, cmd_env
            )
            return json.loads(stdout)
        except UvCommandExecutionError:
            raise UvPipListError("unable to get a list of dependencies")


    def uv_cmd(
            self,
            cmd_args: list[str],
            # run_as_user: str = "pikesquares",
            cmd_env: dict | None = None,
            chdir: Path | None = None,

        ) -> tuple[str, str, str]:
        logger.info(f"[pikesquares] uv_cmd: {cmd_args=}")
        try:
            if cmd_env:
                pl_local.env.update(cmd_env)
                logger.debug(f"{cmd_env=}")

            # with pl_local.as_user(run_as_user):
            with pl_local.cwd(chdir or self.app_root_dir):
                uv = pl_local[str(self.uv_bin)]
                retcode, stdout, stderr = uv.run(
                    cmd_args,
                    **{"env": cmd_env}
                )
                logger.debug(f"[pikesquares] uv_cmd: {retcode=}")
                logger.debug(f"[pikesquares] uv_cmd: {stdout=}")
                logger.debug(f"[pikesquares] uv_cmd: {stderr=}")
                return retcode, stdout, stderr
        except ProcessExecutionError as exc:
            raise exc
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
            #raise UvCommandExecutionError(
            #        f"uv cmd [{' '.join(cmd_args)}] failed.\n{exc.stderr}"
            #)
