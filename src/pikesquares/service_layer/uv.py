import structlog
from aiopath import AsyncPath
from plumbum import ProcessExecutionError
from plumbum import local as pl_local

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

