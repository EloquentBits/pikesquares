from pathlib import Path
import shutil
import tempfile

import pydantic
from rich.console import RenderableType
import structlog

from pikesquares.cli.console import console
from .uv import UVMixin
from . import BaseLanguageRuntime

from .exceptions import (
    UvSyncError,
    UvPipInstallError,
    PythonRuntimeCheckError,
    PythonRuntimeDjangoCheckError,
    PythonRuntimeInitError,
)

logger = structlog.get_logger()


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
            logger.error(f"unable to delete tmp dir @ {str(app_tmp_dir)}")

    def init(
            self,
            venv: Path,
            check: bool = True,
        ) -> bool:
        logger.debug("[pikesquares] PythonRuntime.init")
        if check:
            app_tmp_dir = Path(tempfile.mkdtemp(prefix="pikesquares_", suffix="_py_app"))
            try:
                self.check(app_tmp_dir)
            except (PythonRuntimeCheckError, PythonRuntimeDjangoCheckError):
                logger.error("[pikesquares] -- PythonRuntimeCheckError --")
                raise PythonRuntimeInitError("Python Runtime check failed")

            self.check_cleanup(app_tmp_dir)

        cmd_env = {
            # "UV_CACHE_DIR": str(conf.pv_cache_dir),
            "UV_PROJECT_ENVIRONMENT": str(venv),
        }
        self.create_venv(venv, cmd_env=cmd_env)
        self.install_dependencies()
        return True

    def check(
            self,
            app_tmp_dir: Path,
        ) -> bool:
        # copy project to tmp dir at $TMPDIR
        logger.debug("[pikesquares] PythonRuntime.check")
        console.print(
            f"Inspecting Python project @ {str(self.app_root_dir)}",
            #log_locals=True,
        )
        shutil.copytree(
            self.app_root_dir,
            app_tmp_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*list(self.PY_IGNORE_PATTERNS))
        )
        for p in Path(app_tmp_dir).iterdir():
            logger.debug(p)

        cmd_env = {}
        venv = app_tmp_dir / ".venv"
        self.create_venv(venv=venv, cmd_env=cmd_env)
        try:
            self.install_dependencies(venv=venv, app_tmp_dir=app_tmp_dir)
        except (UvSyncError, UvPipInstallError):
            logger.error("installing dependencies failed.")
            self.check_cleanup(app_tmp_dir)
            raise PythonRuntimeCheckError("uv install dependencies failed.")
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
