import json
import shutil
import traceback
import uuid
from pathlib import Path

import aiofiles
import pluggy
import pydantic
import structlog
import toml
from aiopath import AsyncPath
from plumbum import ProcessExecutionError
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlmodel import Field, Relationship

from pikesquares.domain.base import TimeStampedBase
from pikesquares.hooks.markers import hook_impl
from pikesquares.service_layer.uv import uv_cmd
from pikesquares.exceptions import (
    DjangoCheckError,
    UvSyncError,
    UvPipInstallError,
    UvPipListError,
    UvCommandExecutionError,
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

PY_IGNORE_PATTERNS: set[str] = set(
    {
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
    }
)
py_runtime_emoji: str = ":snake:"


class DjangoCheckMessage(pydantic.BaseModel):
    # 4_0.E001
    id: str
    # ?: (4_0.E001) As of Django 4.0, the values in the CSRF_TRUSTED_ORIGINS setting must start with a scheme (usually http:// or https://) but found . See the release notes for details.
    message: str


class DjangoCheckMessages(pydantic.BaseModel):
    messages: list[DjangoCheckMessage] = []


class DjangoSettings(pydantic.BaseModel):

    # SETTINGS_MODULE = 'mysite.settings'
    # WSGI_APPLICATION = 'mysite.wsgi.application'
    # DATABASES = {'default':
    #   {'ENGINE': 'django.db.backends.sqlite3',
    #       'NAME': PosixPath('/home/pk/dev/eqb/pikesquares-app-templates/sandbox/django/djangotutorial/db.sqlite3'),
    #       'ATOMIC_REQUESTS': False, 'AUTOCOMMIT': True,
    #       'CONN_MAX_AGE': 0, 'CONN_HEALTH_CHECKS': False,
    #       'OPTIONS': {}, 'TIME_ZONE': None, 'USER': '', 'PASSWORD': '', 'HOST': '',
    #       'PORT': '', 'TEST': {'CHARSET': None,
    #       'COLLATION': None, 'MIGRATE': True, 'MIRROR': None, 'NAME': None}}}
    # CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    # ALLOWED_HOSTS = []
    # INSTALLED_APPS = [
    #        'django.contrib.admin',
    #        'django.contrib.auth',
    #        'django.contrib.contenttypes',
    #        'django.contrib.sessions',
    #        'django.contrib.messages',
    #        'django.contrib.staticfiles'
    # ]
    # ROOT_URLCONF = 'mysite.urls'  ###
    # SECRET_KEY = ''
    # STATIC_URL = 'static/'

    settings_module: str
    root_urlconf: str
    wsgi_application: str
    base_dir: Path | None = None

    def settings_with_titles(self) -> list[tuple[str, str]]:
        return [
            ("Django Settings Module", self.settings_module),
            ("Django URLConf Module", self.root_urlconf),
            ("Django WSGI Module", self.wsgi_application),
        ]




class AppRuntime(AsyncAttrs, TimeStampedBase):
    """Base App Runtime SQL model class."""

    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4()),
        max_length=36,
    )
    version: str = Field(max_length=25)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class Bugsink:

    @hook_impl
    def get_repo_url(self, service_name: str) -> str | None:
        logger.debug(f"Bugsink: get_repo_url: {service_name=}")
        if service_name == "bugsink":
            return "https://github.com/bugsink/bugsink.git"

    @hook_impl
    def python_app_codebase_before_install_dependencies(
        self,
        service_name: str,
    ) -> None:
        if service_name != "bugsink":
            return

        logger.info("Bugsink python_app_codebase_before_install_dependencies")

class Meshdb:

    @hook_impl
    def get_repo_url(self, service_name: str) -> str | None:
        logger.debug(f"Meshdb: get_repo_url: {service_name=}")
        if service_name == "meshdb":
            return "https://github.com/meshnyc/meshdb.git"

    @hook_impl
    def python_app_codebase_before_install_dependencies(
        self,
        service_name: str,
    ) -> None:
        if service_name != "meshdb":
            return

        logger.info("Meshdb python_app_codebase_before_install_dependencies")


class BaseAppCodebase(AsyncAttrs, TimeStampedBase):

    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4()),
        max_length=36,
    )
    root_dir: str = Field(max_length=255)
    repo_dir: str = Field(max_length=255)
    repo_git_url: str = Field(max_length=255)
    venv_dir: str = Field(max_length=255)
    editable_mode: bool = Field(default=False)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class PythonAppCodebase(BaseAppCodebase, table=True):

    __tablename__ = "python_app_codebases"

    uv_bin: str = Field(max_length=255)
    wsgi_apps: list["WsgiApp"] = Relationship(back_populates="python_app_codebase")

    async def get_files(self) -> set[AsyncPath]:
        all_files: set[AsyncPath] = set()
        for ext in PY_MATCH_FILES:
            try:
                all_files.add(
                    next(
                        await AsyncPath(self.repo_dir).glob(ext)
                    )
                )
            except StopIteration:
                continue
        return all_files

    async def get_top_level_files(self) -> set[AsyncPath]:
        return await self.get_files()

    async def top_level_file_names(self) -> set[str]:
        return {f.name for f in await self.get_top_level_files()}

    async def check_cleanup(self, app_tmp_dir: AsyncPath) -> None:
        try:
            shutil.rmtree(app_tmp_dir)
        except OSError:
            logger.error(f"unable to delete tmp dir @ {str(app_tmp_dir)}")

    async def detect_version(self) -> str:
        try:
            version_file = AsyncPath(self.app_repo_dir) / ".python-version"
            _ver = await version_file.read_text()
            return _ver.strip()
        except FileNotFoundError:
            return "3.12"

    async def detect_deps(
        self,
        service_name: str,
        plugin_manager: pluggy.PluginManager
    ) -> bool | None:

        async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
            #filename = os.path.join(d, "file.ext")
            app_tmp_dir = AsyncPath(tmp_dir)
            shutil.copytree(
                self.root_dir,
                app_tmp_dir,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*list(PY_IGNORE_PATTERNS)),
            )
            # for p in AsyncPath(app_tmp_dir).iterdir():
            #    logger.debug(p)
            # Detect Project Dependencies
            #cmd_env = {}
            #await self.create_venv(
            #    venv=app_tmp_dir / ".venv",
            #    cmd_env=cmd_env,
            #)
            logger.info(f"created a tmp dir {app_tmp_dir}")

            try:
                plugin_manager.hook.\
                    python_app_codebase_before_install_dependencies(
                        service_name=service_name,
                    )
                logger.info(f"installing deps into tmp dir {app_tmp_dir}")
                await self.install_dependencies(
                    venv=app_tmp_dir / ".venv",
                    app_tmp_dir=app_tmp_dir,
                )
                logger.info(f"installed deps into tmp dir {app_tmp_dir}")
            except (UvSyncError, UvPipInstallError):
                logger.error("installing dependencies failed.")
                #await self.check_cleanup(app_tmp_dir)
                return

            try:
                dependencies_count = len(await self.dependencies_list())
                logger.info(f"{dependencies_count} dependencies detected")
            except UvPipListError as exc:
                logger.error(exc)
                traceback.format_exc()

            return True

    async def read_pyproject_toml(self):
        with open(AsyncPath(self.root_dir) / "pyproject.toml", "r") as f:
            config = toml.load(f)
            deps = config["project"]["dependencies"]
            print("[pikesquares] located deps in pyproject.toml")
            print(deps)


    async def install_dependencies(
        self,
        cmd_env: dict | None = None,
        venv: AsyncPath | None = None,
        app_tmp_dir: AsyncPath | None = None,
        ) -> None:

        logger.info(f"uv installing dependencies in venv @ {venv}")
        cmd_args = []
        install_inspect_extensions = False

        #if "uv.lock" and "pyproject.toml" in self.top_level_file_names:
        #    logger.info("installing dependencies from uv.lock")
        try:
            retcode, stdout, stderr = await uv_cmd(
                AsyncPath(self.uv_bin),
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
                chdir=str(app_tmp_dir) or self.repo_dir,
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
                retcode, stdout, stderr = uv_cmd(
                    AsyncPath(self.uv_bin),
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
                    retcode, stdout, stderr = uv_cmd(
                        AsyncPath(self.uv_bin),
                        cmd_args,
                        cmd_env
                    )
                except UvCommandExecutionError:
                    raise UvPipInstallError("unable to install inspect-extensions in")
        #else:
        #    raise PythonRuntimeDepsInstallError("unable to install Python runtime dependencies")

    async def dependencies_list(self):
        cmd_env = {}
        cmd_args = ["pip", "list", "--format", "json"]
        try:
            retcode, stdout, stderr = await uv_cmd(
                AsyncPath(self.uv_bin),
                cmd_args,
                cmd_env,
            )
            return json.loads(stdout)
        except UvCommandExecutionError:
            raise UvPipListError("unable to get a list of dependencies")

    """
    async def init(
        self,
        venv: AsyncPath,
        check: bool = True,
    ) -> bool:
        logger.debug("[pikesquares] PythonRuntime.init")
        if check:
            app_tmp_dir = AsyncPath(
                tempfile.mkdtemp(prefix="pikesquares_", suffix="_py_app")
            )
            try:
                await self.check(app_tmp_dir)
            except (PythonRuntimeCheckError, PythonRuntimeDjangoCheckError):
                logger.error("[pikesquares] -- PythonRuntimeCheckError --")
                raise PythonRuntimeInitError("Python Runtime check failed")

            await self.check_cleanup(app_tmp_dir)

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
        app_tmp_dir: AsyncPath,
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
        for p in await AsyncPath(app_tmp_dir).iterdir():
            logger.debug(p)

        cmd_env = {}
        venv = app_tmp_dir / ".venv"
        self.create_venv(venv=venv, cmd_env=cmd_env)
        try:
            self.install_dependencies(venv=venv, app_tmp_dir=app_tmp_dir)
        except (UvSyncError, UvPipInstallError):
            logger.error("installing dependencies failed.")
            await self.check_cleanup(app_tmp_dir)
            raise PythonRuntimeCheckError("uv install dependencies failed.")
        return True
        """

    async def is_django(self, app_repo_dir: AsyncPath) -> bool:
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
            all_django_files = await AsyncPath(app_repo_dir).glob(f"**/{filename}")
            all_files.extend(
                list(filter(lambda f: ".venv" not in Path(f).parts, all_django_files))
            )
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
    async def create_venv(
        self,
        venv: AsyncPath,
        cmd_env: dict | None = None,
        ) -> None:
        logger.info("Creating Python virtual environment")
        logger.debug(f"`uv venv`: {venv}")

        # os.chdir(app_root_dir)
        cmd_args = []

        try:
            retcode, stdout, stderr = await uv_cmd(
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

    def run_app_init_command(
        self,
        cmd_args: list[str],
        cmd_env: dict | None = None
        ) -> tuple[str, str, str]:

        logger.info(f"failed: uv run {' '.join(cmd_args)}")
        try:
            retcode, stdout, stderr = uv_cmd(
                AsyncPath(self.uv_bin),
                [
                    "run",
                    "--verbose",
                    "--python",
                    "/usr/bin/python3",
                    "--color", "never",
                    *cmd_args,
                ],
                cmd_env=cmd_env,
                chdir=AsyncPath(self.repo_dir),
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

    async def django_check(
        self,
        cmd_env: dict | None = None,
        app_tmp_dir: AsyncPath | None = None,
    ) -> DjangoCheckMessages:
        chdir = str(app_tmp_dir) or self.root_dir
        logger.info(f"[pikesquares] run django check in {str(chdir)}")
        dj_msgs = DjangoCheckMessages()

        # DJANGO_SETTINGS_MODULE=mysite.settings
        # uv run python -c "from django.conf import settings ; print(settings.WSGI_APPLICATION)"
        cmd_args = ["run", "manage.py", "check"]
        try:
            retcode, stdout, stderr = await uv_cmd(
                AsyncPath(self.uv_bin),
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

    async def django_diffsettings(
        self,
        cmd_env: dict | None = None,
        app_tmp_dir: AsyncPath | None = None,
    ) -> DjangoSettings:
        logger.info("[pikesquares] django diffsettings")
        cmd_args = ["run", "manage.py", "diffsettings"]
        chdir = str(app_tmp_dir) or self.root_dir
        try:
            retcode, stdout, stderr = await uv_cmd(
                AsyncPath(self.uv_bin),
                cmd_args,
                cmd_env,
                chdir=chdir,
            )
            dj_settings = {}
            for line in stdout.splitlines():
                for fld in DjangoSettings.model_fields.keys():
                    if fld.upper() in line:
                        match = re.search(fr"{fld.upper()}\s*=\s*['\"](.*?)['\"]", line)
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

