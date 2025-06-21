import json

import structlog
from aiopath import AsyncPath
from plumbum import ProcessExecutionError
from plumbum import local as pl_local

from pikesquares.exceptions import (
    UvCommandExecutionError,
    UvPipInstallError,
    UvSyncError,
    UvPipListError,
)

logger = structlog.getLogger()


async def uv_cmd(
        uv_bin: AsyncPath,
        cmd_args: list[str],
        # run_as_user: str = "pikesquares",
        cmd_env: dict | None = None,
        chdir: AsyncPath | None = None,

    ) -> tuple[str, str, str]:
    logger.info(f"[pikesquares] uv_cmd: {cmd_args=}")
    try:
        if cmd_env:
            pl_local.env.update(cmd_env)
            logger.debug(f"{cmd_env=}")

        # with pl_local.as_user(run_as_user):
        with pl_local.cwd(chdir):
            uv = pl_local[str(uv_bin)]
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

async def uv_dependencies_install(
    uv_bin: AsyncPath,
    venv: AsyncPath,
    repo_dir: AsyncPath,
    cmd_env: dict | None = None,
    ) -> None:

    logger.info(f"uv installing dependencies in venv @ {venv}")
    cmd_args = []
    install_inspect_extensions = False

    #if "uv.lock" and "pyproject.toml" in self.top_level_file_names:
    #    logger.info("installing dependencies from uv.lock")
    assert await repo_dir.exists(), f"repo dir {repo_dir} does not exist"
    try:
        retcode, stdout, stderr = await uv_cmd(
            AsyncPath(uv_bin),
            [
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
            chdir=repo_dir,
        )
        #print(retcode)
        #print(stdout)
        #print(stderr)
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
            retcode, stdout, stderr = await uv_cmd(
                AsyncPath(uv_bin),
                cmd_args,
                cmd_env=cmd_env,
                chdir=repo_dir,
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
                retcode, stdout, stderr = await uv_cmd(
                    AsyncPath(uv_bin),
                    cmd_args,
                    cmd_env
                )
            except UvCommandExecutionError:
                raise UvPipInstallError("unable to install inspect-extensions in")
    #else:
    #    raise PythonRuntimeDepsInstallError("unable to install Python runtime dependencies")
    #
async def uv_dependencies_list(
    uv_bin: AsyncPath,

):
    cmd_env = {}
    cmd_args = ["pip", "list", "--format", "json"]
    try:
        retcode, stdout, stderr = await uv_cmd(
            AsyncPath(uv_bin),
            cmd_args,
            cmd_env,
        )
        return json.loads(stdout)
    except UvCommandExecutionError:
        raise UvPipListError("unable to get a list of dependencies")

