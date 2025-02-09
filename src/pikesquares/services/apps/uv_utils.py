from pathlib import Path

from plumbum import local as pl_local
from plumbum import ProcessExecutionError


class UvExecError(Exception):
    pass


class UVCommandExecutionError(Exception):
    pass


def uv_cmd(
        uv_bin: Path,
        cmd_args: list[str],
        app_root_dir: Path,
        run_as_user: str = "pikesquares",
        cmd_env: dict | None = None,

    ):
    print(f"[pikesquares] uv_cmd: {cmd_args=}")
    try:
        print(type(pl_local))
        if cmd_env:
            pl_local.env.update(cmd_env)

        print(f"{cmd_env=}")

        # with pl_local.as_user(run_as_user):
        with pl_local.cwd(app_root_dir):
            uv = pl_local[str(uv_bin)]
            retcode, stdout, stderr = uv.run(
                cmd_args,
                **{"env": cmd_env}
            )
            print(f"[pikesquares] {retcode=}")
            print(f"[pikesquares] {stdout=}")
            print(f"[pikesquares] {stderr=}")
            return retcode, stdout, stderr
    except ProcessExecutionError as exc:
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
        raise UVCommandExecutionError(f"uv cmd [{' '.join(cmd_args)}] failed.\n{exc.stderr}")
