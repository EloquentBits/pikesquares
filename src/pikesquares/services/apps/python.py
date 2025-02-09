import traceback
import tempfile
import shutil
from pathlib import Path

import pydantic

from .django import PythonRuntimeDjangoMixin
from .uv import UVMixin
from . import BaseLanguageRuntime

from .exceptions import (
    UvSyncError,
    UvPipInstallError,
    DjangoDiffSettingsError,
    DjangoCheckError,
    PythonRuntimeCheckError,
    PythonRuntimeInitError,
)


class PythonRuntime(BaseLanguageRuntime, PythonRuntimeDjangoMixin, UVMixin):

    uv_bin: Path | None = None

    MATCH_FILES: set[str] = set({
        "main.py",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "Pipfile.lock",
        "uv.lock",
    })

    PY_IGNORE_PATTERNS: set[str] = set({
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
    })

    @pydantic.computed_field
    def version(self) -> str:
        try:
            return (self.app_root_dir / ".python-version").\
                read_text().strip()
        except FileNotFoundError:
            return "3.12"

    def check_cleanup(self, app_tmp_dir: Path) -> None:
        try:
            shutil.rmtree(app_tmp_dir)
        except OSError:
            print(f"unable to delete tmp dir @ {str(app_tmp_dir)}")

    def check(self) -> bool:
        app_tmp_dir = Path(tempfile.mkdtemp(prefix="pikesquares_", suffix="_py_app"))
        # copy project to tmp dir at $TMPDIR
        shutil.copytree(
            self.app_root_dir,
            app_tmp_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*list(self.PY_IGNORE_PATTERNS))
        )
        for p in Path(app_tmp_dir).iterdir():
            print(p)

        cmd_env = {}
        venv = app_tmp_dir / ".venv"
        self.create_venv(venv=venv, cmd_env=cmd_env)

        try:
            self.install_dependencies(venv=venv, app_tmp_dir=app_tmp_dir)
        except (UvSyncError, UvPipInstallError):
            print(traceback.format_exc())
            self.check_cleanup(app_tmp_dir)
            raise PythonRuntimeCheckError("django uv install dependencies failed.")

        if self.is_django(app_tmp_dir=app_tmp_dir):
            print("[pikesquares] detected Django project.")
            try:
                self.django_check(app_tmp_dir=app_tmp_dir)
            except DjangoCheckError:
                print(traceback.format_exc())
                self.check_cleanup(app_tmp_dir)
                raise PythonRuntimeCheckError("django check command failed")
            try:
                django_settings = self.django_diffsettings(app_tmp_dir=app_tmp_dir)
                print(f"{django_settings=}")
                self.collected_project_metadata = {
                        django_settings.__class__.__name__: django_settings,
                }
            except DjangoDiffSettingsError:
                print(traceback.format_exc())
                self.check_cleanup(app_tmp_dir)
                raise PythonRuntimeCheckError("django diffsettings command failed.")

        print(f"[pikesquares] {self.version=}")
        print(f"[pikesquares] removing {str(app_tmp_dir)}")
        self.check_cleanup(app_tmp_dir)
        return True

    def init(self, venv: Path | None = None) -> bool:
        try:
            self.check()
        except PythonRuntimeCheckError:
            print("[pikesquares] -- PythonRuntimeCheckError --")
            print(traceback.format_exc())
            raise PythonRuntimeInitError("Python Runtime check failed")

        cmd_env = {
            # FIXME does not have any effect.
            # "UV_CACHE_DIR": str(conf.uv_cache_dir),
            "UV_PROJECT_ENVIRONMENT": str(venv),
        }
        self.create_venv(venv, cmd_env=cmd_env)
        self.install_dependencies()

        return True
