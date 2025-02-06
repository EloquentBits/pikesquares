from pathlib import Path

from plumbum import local as plumbum_local
from plumbum import ProcessExecutionError


class UvExecError(Exception):
    pass


class UVCommandExecutionError(Exception):
    pass


def uv_cmd(
        uv_bin: Path,
        cmd_args: list[str],
        cmd_env: dict,
        app_root_dir: Path
    ):
    print(f"[pikesquares] uv_cmd: {cmd_args=}")
    try:
        with plumbum_local.cwd(app_root_dir):
            uv = plumbum_local[str(uv_bin)]
            retcode, stdout, stderr = uv.run(cmd_args)
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
