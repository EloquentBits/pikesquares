import re
import shutil
import tempfile
import traceback
from pathlib import Path

import giturlparse
import pluggy
import structlog
import toml
from plumbum import ProcessExecutionError
from sqlmodel import Field, Relationship

from pikesquares.domain.codebase import BaseAppCodebase
from pikesquares.domain.python_django_codebase import (
    DjangoCheckMessage,
    DjangoCheckMessages,
    DjangoSettings,
)
from pikesquares.exceptions import (
    DjangoCheckError,
    DjangoDiffSettingsError,
    UvCommandExecutionError,
    UvPipInstallError,
    UvPipListError,
    UvSyncError,
)
from pikesquares.service_layer.uv import (
    uv_cmd,
    uv_dependencies_install,
    uv_dependencies_list,
)

logger = structlog.getLogger()

PY_MATCH_FILES: set[str] = set(
    {
        "main.py",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "Pipfile.lock",
        "uv.lock",
    }
)

PY_TMP_DIR_IGNORE_PATTERNS: set[str] = set(
    {
        "*.pyc",
        "*.sqlite*",
        "tmp*",
        "venv",
        ".venv",
        "tests",
        "__pycache__",
        # ".gitignore",
        # ".git",
        # "README*",
        # "LICENSE",
    }
)
py_runtime_emoji: str = ":snake:"


class PythonAppCodebase(BaseAppCodebase, table=True):
    __tablename__ = "python_app_codebases"

    uv_bin: str | None = Field(max_length=255)
    wsgi_apps: list["WsgiApp"] = Relationship(back_populates="python_app_codebase")

    root_dir: str = Field(max_length=255)
    wsgi_file: str | None = Field(max_length=255)
    wsgi_module: str | None = Field(max_length=50)

    def get_files(self) -> set[Path]:
        all_files: set[Path] = set()
        for ext in PY_MATCH_FILES:
            try:
                all_files.add(next(Path(self.repo_dir).glob(ext)))
            except StopIteration:
                continue
        return all_files

    def get_top_level_files(self) -> set[Path]:
        return self.get_files()

    def top_level_file_names(self) -> set[str]:
        return {f.name for f in self.get_top_level_files()}

    def check_cleanup(self, app_tmp_dir: Path) -> None:
        try:
            shutil.rmtree(app_tmp_dir)
        except OSError:
            logger.error(f"unable to delete tmp dir @ {str(app_tmp_dir)}")

    def detect_version(self) -> str:
        try:
            version_file = Path(self.app_repo_dir) / ".python-version"
            _ver = version_file.read_text()
            return _ver.strip()
        except FileNotFoundError:
            return "3.12"

    def read_pyproject_toml(self):
        with open(Path(self.root_dir) / "pyproject.toml", "r") as f:
            config = toml.load(f)
            deps = config["project"]["dependencies"]
            print("[pikesquares] located deps in pyproject.toml")
            print(deps)

    @property
    def repo_name(self) -> str:
        if giturlparse.validate(self.repo_git_url):
            giturl = giturlparse.parse(self.repo_git_url)
            return giturl.name
        raise ValueError(f"invalid git repo url {self.repo_git_url}")

    def dependencies_validate(self) -> bool | None:
        """
        copy repo into a temporary directory and attempt to run `uv sync`
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            app_tmp_dir = Path(tmp_dir)
            logger.info(f"created a tmp dir {app_tmp_dir}")
            # filename = os.path.join(d, "file.ext")
            shutil.copytree(
                self.root_dir,
                app_tmp_dir,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*list(PY_TMP_DIR_IGNORE_PATTERNS)),
            )
            logger.info(f"coppied {self.root_dir} into {app_tmp_dir}")
            app_root_dir = app_tmp_dir / self.repo_name
            logger.info(f"{app_root_dir=}")
            try:
                logger.info(f"installing deps into tmp dir {app_root_dir}")
                uv_dependencies_install(
                    uv_bin=Path(self.uv_bin),
                    venv=app_root_dir / ".venv",
                    repo_dir=app_root_dir,
                )
                logger.info(f"installed deps into tmp dir {app_root_dir}")
            except (UvSyncError, UvPipInstallError):
                logger.error("installing dependencies failed.")
                # self.check_cleanup(app_tmp_dir)
                return

            if 0:
                try:
                    dependencies_count = len(uv_dependencies_list(Path(self.uv_bin)))
                    logger.info(f"{dependencies_count} dependencies detected")
                except UvPipListError as exc:
                    logger.error(exc)
                    traceback.format_exc()

            return True

    def dependencies_install(self, service_name, plugin_manager: pluggy.PluginManager) -> bool | None:

        plugin_manager.hook.before_dependencies_install(
            service_name=service_name,
            uv_bin=Path(self.uv_bin),
            repo_dir=Path(self.repo_dir),
        )
        try:
            if not Path(self.venv_dir).exists():
                logger.info(f"installing deps into dir {self.repo_dir}")
                uv_dependencies_install(
                    uv_bin=Path(self.uv_bin),
                    venv=Path(self.venv_dir),
                    repo_dir=Path(self.repo_dir),
                )
                logger.info(f"installed deps into dir {self.repo_dir}")
            else:
                logger.info(f"skipping installing deps into dir {self.repo_dir}")
        except (UvSyncError, UvPipInstallError):
            logger.error("installing dependencies failed.")
            # self.check_cleanup(app_tmp_dir)

        plugin_manager.hook.after_dependencies_install(
            service_name=service_name,
            uv_bin=Path(self.uv_bin),
            repo_dir=Path(self.repo_dir),
        )

        return True

    """
    def init(
        self,
        venv: Path,
        check: bool = True,
    ) -> bool:
        logger.debug("[pikesquares] PythonRuntime.init")
        if check:
            app_tmp_dir = Path(
                tempfile.mkdtemp(prefix="pikesquares_", suffix="_py_app")
            )
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
    """

    """
    def check(
        self,
        app_tmp_dir: Path,
    ) -> bool:
        # copy project to tmp dir at $TMPDIR
        logger.debug("[pikesquares] PythonRuntime.check")
        logger.info(
            f"Inspecting Python project @ {self.repo_dir}",
            # log_locals=True,
        )
        shutil.copytree(
            self.repo_dir,
            app_tmp_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*list(PY_IGNORE_PATTERNS)),
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
        """

    def is_django(self, app_repo_dir: Path) -> bool:
        py_django_files: set[str] = set(
            {
                "urls.py",
                "wsgi.py",
                "settings.py",
                "manage.py",
            }
        )
        all_files = []
        for filename in py_django_files:
            all_django_files = Path(app_repo_dir).glob(f"**/{filename}")
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

    """
    def create_venv(
        self,
        venv: Path,
        cmd_env: dict | None = None,
        ) -> None:
        logger.info("Creating Python virtual environment")
        logger.debug(f"`uv venv`: {venv}")

        # os.chdir(app_root_dir)
        cmd_args = []

        try:
            retcode, stdout, stderr = uv_cmd(
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
            raise UvSyncError(f"`uv venv` unable to create venv in {venv}")
    """

    def run_app_init_command(self, cmd_args: list[str], cmd_env: dict | None = None) -> tuple[str, str, str]:

        logger.info(f"failed: uv run {' '.join(cmd_args)}")
        try:
            retcode, stdout, stderr = uv_cmd(
                Path(self.uv_bin),
                [
                    "run",
                    "--verbose",
                    "--python",
                    "/usr/bin/python3",
                    "--color",
                    "never",
                    *cmd_args,
                ],
                cmd_env=cmd_env,
                chdir=Path(self.repo_dir),
            )
            return retcode, stdout, stderr
        except ProcessExecutionError as exc:
            logger.exception(exc)
            raise UvCommandExecutionError(f"uv run {' '.join(cmd_args)}")

    """
    def check(self, app_tmp_dir: Path) -> bool:
        logger.debug("[pikesquares] PythonRuntimeDjango.check")
        if super().check(app_tmp_dir):
            logger.debug("[pikesquares] PythonRuntimeDjango.check | PythonRuntime check ok")
            # console_status.update(status="[magenta]Provisioning Python WSGI App", spinner="earth")
            try:
                self.collected_project_metadata["django_check_messages"] = self.django_check(app_tmp_dir=app_tmp_dir)
            except DjangoCheckError:
                self.check_cleanup(app_tmp_dir)
                raise PythonRuntimeDjangoCheckError("django check command failed")
            try:
                self.collected_project_metadata["django_settings"] = self.django_diffsettings(app_tmp_dir=app_tmp_dir)
            except DjangoDiffSettingsError:
                self.check_cleanup(app_tmp_dir)
                raise PythonRuntimeDjangoCheckError("django diffsettings command failed.")
            return True
        return False
    """

    def django_check(
        self,
        cmd_env: dict | None = None,
        app_tmp_dir: Path | None = None,
    ) -> DjangoCheckMessages:
        chdir = str(app_tmp_dir) or self.root_dir
        logger.info(f"[pikesquares] run django check in {str(chdir)}")
        dj_msgs = DjangoCheckMessages()

        # DJANGO_SETTINGS_MODULE=mysite.settings
        # uv run python -c "from django.conf import settings ; print(settings.WSGI_APPLICATION)"
        cmd_args = ["run", "manage.py", "check"]
        try:
            retcode, stdout, stderr = uv_cmd(
                Path(self.uv_bin),
                cmd_args,
                cmd_env,
                chdir=chdir,
            )
            if "System check identified no issues" in stdout:
                return dj_msgs
        except ProcessExecutionError as plumbum_pe_err:
            logger.error(" =============== ProcessExecutionError ==============")
            # https://docs.djangoproject.com/en/5.1/ref/checks/#checkmessage
            # id
            # Optional string. A unique identifier for the issue.
            # Identifiers should follow the pattern applabel.X001, where X is one of the letters CEWID,
            # indicating the message severity (C for criticals, E for errors and so).
            # The number can be allocated by the application, but should be unique within that application.

            # if "staticfiles.W004" in plumbum_pe_err.stderr:
            # The directory '/tmp/pre_icugrao4_suf/static' in the STATICFILES_DIRS
            # create static dir
            #    match = re.search(r"/tmp/pikesquares_[a-zA-Z0-9]+_py_app/static", plumbum_pe_err.stderr)
            #    if match:
            #        print(f"[pikesquares] creating staticfiles directory {match.group()}")
            #        try:
            #            Path(match.group()).mkdir()
            #        except:
            #            traceback.format_exc()
            #            raise DjangoCheckError(f"Django check: unable to create staticfiles directory {match.group()}")
            #        else:
            #            print("[pikesquares] re-running Django check")
            #            self.django_check(app_tmp_dir or self.app_root_dir)

            logger.error(plumbum_pe_err.stderr)
            logger.error(" =============== /ProcessExecutionError ==============")
            if plumbum_pe_err.stderr.startswith("SystemCheckError"):
                err_lines = plumbum_pe_err.stderr.split("\n")
                for msg in [line for line in err_lines if line.startswith("?:")]:
                    try:
                        # ?: (4_0.E001)
                        msg_id = re.findall(r"(?<=\()[^)]+(?=\))", msg)[0]
                    except IndexError:
                        logger.error(f"unable to parse message id from '{msg}'")
                        continue
                    dj_msgs.messages.append(
                        DjangoCheckMessage(
                            id=msg_id,
                            message="".join(
                                msg.split(")")[1:],
                            ).strip(),
                        )
                    )
                return dj_msgs
            else:
                raise DjangoCheckError(
                    f"[pikesquares] UvExecError: unable to run django check in {str(chdir)}"
                ) from None

        logger.info(f"django check completed. no errors.: {retcode=} {stdout=} {stderr=}")
        return dj_msgs

    def django_diffsettings(
        self,
        cmd_env: dict | None = None,
        app_tmp_dir: Path | None = None,
    ) -> DjangoSettings:
        logger.info("[pikesquares] django diffsettings")
        cmd_args = ["run", "manage.py", "diffsettings"]
        chdir = str(app_tmp_dir) or self.root_dir
        try:
            retcode, stdout, stderr = uv_cmd(
                Path(self.uv_bin),
                cmd_args,
                cmd_env,
                chdir=chdir,
            )
            dj_settings = {}
            for line in stdout.splitlines():
                for fld in DjangoSettings.model_fields.keys():
                    if fld.upper() in line:
                        match = re.search(rf"{fld.upper()}\s*=\s*['\"](.*?)['\"]", line)
                        if match:
                            dj_settings[fld] = match.group(1)
                        else:
                            logger.debug(f"did not find a match for {fld}")

            assert dj_settings
            django_settings = DjangoSettings(**dj_settings)
            logger.debug(django_settings.model_dump())
            return django_settings

        except UvCommandExecutionError:
            raise DjangoDiffSettingsError(f"[pikesquares] UvExecError: unable to run django diffsettings in {chdir}")
