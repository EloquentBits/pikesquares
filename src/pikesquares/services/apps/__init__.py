import os
import sys
import shutil
from pathlib import Path

import toml

from .uv_utils import uv_cmd
# from wsgi import WsgiApp

# __all__ = (
#    "WsgiApp",
# )

PY_IGNORE_PATTERNS = [
    "*.pyc",
    ".gitignore",
    "*.sqlite*",
    "README*",
    "LICENSE",
    "tmp*",
    ".git",
    "venv",
    ".venv",
    "tests",
    "__pycache__",
]


class UvExecError(Exception):
    pass


class UVCommandExecutionError(Exception):
    pass


class LanguageRuntime:
    pass


class PythonRuntime(LanguageRuntime):
    MATCH_FILES = set({
        "main.py",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "Pipfile.lock",
        "uv.lock",
    })

    def install_dependencies(self, app_root_dir: Path, top_level_file_names: set[str], uv_bin: Path) -> None:
        print(f"[pikesquares] uv_install_deps: {str(app_root_dir)}")

        os.chdir(app_root_dir)
        cmd_env = {}
        cmd_args = []
        install_inspect_extensions = False

        if 0:
            print(f"[pikesquares] creating venv in {str(app_root_dir / '.venv')}")
            try:
                retcode, stdout, stderr = uv_cmd(uv_bin, [*cmd_args, "venv", "--verbose"], cmd_env, app_root_dir)
            except UvExecError:
                print(f"[pikesquares] unable to create venv in {str(app_root_dir)}")
                shutil.rmtree(app_root_dir)
                sys.exit(1)

        if "uv.lock" in top_level_file_names:
            print("[pikesquares] installing dependencies from uv.lock")
            try:
                retcode, stdout, stderr = uv_cmd(uv_bin, [*cmd_args, "sync", "--verbose"], cmd_env, app_root_dir)
            except UvExecError:
                print(f"[pikesquares] unable to install dependencies in {str(app_root_dir)}")
                sys.exit(1)

        elif "requirements.txt" in top_level_file_names:
            # uv pip install -r requirements.txt
            # uv add -r requirements.txt
            # uv export --format requirements-txt
            print("[pikesquares] installing depedencies from requirements.txt")
            cmd_args = [*cmd_args, "pip", "install", "-r", "requirements.txt"]
            try:
                retcode, stdout, stderr = uv_cmd(uv_bin, cmd_args, cmd_env, app_root_dir)
            except UvExecError:
                print("[pikesquares] UvExecError: unable to install dependencies from requirements.txt")
                shutil.rmtree(app_root_dir)
                sys.exit(1)
                #for p in Path(app_root_dir / ".venv/lib/python3.12/site-packages").iterdir():
                #    print(p)
            if install_inspect_extensions:
                print("[pikesquares] installing inspect-extensions")
                cmd_args = [*cmd_args, "pip", "install", "inspect-extensions"]
                try:
                    retcode, stdout, stderr = uv_cmd(uv_bin, cmd_args, cmd_env, app_root_dir)
                except UvExecError:
                    print(f"[pikesquares] UvExecError: unable to install inspect-extensions in {str(app_root_dir)}")
                    shutil.rmtree(app_root_dir)
                    sys.exit(1)

        if "pyproject.toml" in top_level_file_names:
            with open(app_root_dir / "pyproject.toml", "r") as f:
                config = toml.load(f)
                deps = config["project"]["dependencies"]
                print("[pikesquares] located deps in pyproject.toml")
                print(deps)


class RubyRuntime(LanguageRuntime):
    MATCH_FILES = set({
        "config.ru",
        "Gemfile",
    })


class PHPRuntime(LanguageRuntime):
    MATCH_FILES = set({
        "index.php",
    })
