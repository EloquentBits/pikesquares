import traceback
import tempfile
import shutil
from pathlib import Path

import pydantic

from .uv import UVMixin
from . import BaseLanguageRuntime

from .exceptions import (
    UvSyncError,
    UvPipInstallError,
    DjangoDiffSettingsError,
    DjangoCheckError,
    PythonRuntimeCheckError,
    PythonRuntimeDjangoCheckError,
    PythonRuntimeInitError,
)


class PythonRuntime(BaseLanguageRuntime, UVMixin):

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

    def check(self, app_tmp_dir: Path) -> bool:
        # copy project to tmp dir at $TMPDIR
        print(f"[pikesquares] PythonRuntime.check")
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
        return True

    def init(self, venv: Path | None = None) -> bool:
        print(f"[pikesquares] PythonRuntime.init")
        app_tmp_dir = Path(tempfile.mkdtemp(prefix="pikesquares_", suffix="_py_app"))
        try:
            self.check(app_tmp_dir)
        except (PythonRuntimeCheckError, PythonRuntimeDjangoCheckError):
            print("[pikesquares] -- PythonRuntimeCheckError --")
            print(traceback.format_exc())
            raise PythonRuntimeInitError("Python Runtime check failed")

        self.check_cleanup(app_tmp_dir)

        cmd_env = {
            # FIXME does not have any effect.
            # "UV_CACHE_DIR": str(conf.uv_cache_dir),
            "UV_PROJECT_ENVIRONMENT": str(venv),
        }
        self.create_venv(venv, cmd_env=cmd_env)
        self.install_dependencies()

        return True

    @classmethod
    def is_django(cls, app_root_dir: Path) -> bool:
        py_django_files: set[str] = set({
            "urls.py",
            "wsgi.py",
            "settings.py",
            "manage.py",
        })
        all_files = []
        for filename in py_django_files:
            all_django_files = Path(app_root_dir).glob(f"**/{filename}")
            all_files.extend(list(filter(lambda f: ".venv" not in Path(f).parts, all_django_files)))
        # for f in all_files:
        #    print(f)
        return bool(len(all_files))

        # for f in glob(f"{app_temp_dir}/**/*wsgi*.py", recursive=True):
        #    print(f)
        # [f for f in glob("**/settings.py", recursive=True) if not f.startswith("venv/")]
        # for f in glob(f"{app_temp_dir}/**/settings.py", recursive=True):
        #    settings_module_path = Path(f)
        #    print(f"settings module: {(settings_module_path)}")
        #    print(f"settings module: {settings_module_path.relative_to(app_temp_dir)}")
        # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecomproject.settings')
