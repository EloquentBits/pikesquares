import re
from pathlib import Path

import pydantic
from plumbum import ProcessExecutionError
from tinydb import TinyDB
import structlog

from pikesquares.conf import AppConfig
from . import Task
from ..data import Router, WsgiAppOptions
from .wsgi import WsgiApp
from .python import PythonRuntime
from .exceptions import (
    UvCommandExecutionError,
    DjangoCheckError,
    DjangoDiffSettingsError,
    PythonRuntimeDjangoCheckError,
)

logger = structlog.get_logger()


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
             ("Django WSGI Module", self.wsgi_application)
        ]


class DjangoWsgiApp(WsgiApp):
    pass


"""
[pikesquares] PythonRuntimeDjango.init
[pikesquares] PythonRuntime.init
[pikesquares] PythonRuntimeDjango.check
[pikesquares] PythonRuntime.check

"""



class PythonRuntimeDjango(PythonRuntime):

    framework_emoji: str = ":unicorn_face:"

    def init(
            self,
            venv: Path,
            check: bool = True,
        ) -> bool:
        logger.debug("[pikesquares] PythonRuntimeDjango.init")
        if super().init(venv, check=check):
            return True
        return False

    def get_tasks(self) -> list:
        tasks = super().get_tasks()
        dj_check_task = Task(
            description="Running Django check",
            visible=False,
            total=1,
            start=False,
            emoji_fld=getattr(self, "framework_emoji", self.runtime_emoji),
            result_mark_fld="",
            description_done="Django check passed",
        )
        dj_settings_task = Task(
            description="Django discovering modules",
            visible=False,
            total=1,
            start=False,
            emoji_fld=getattr(self, "framework_emoji", self.runtime_emoji),
            result_mark_fld="",
            description_done="Django modules discovered",
        )
        return [*tasks, dj_check_task, dj_settings_task]

    def check(
            self,
            app_tmp_dir: Path
        ) -> bool:
        logger.debug("[pikesquares] PythonRuntimeDjango.check")
        if super().check(app_tmp_dir):
            logger.debug("[pikesquares] PythonRuntimeDjango.check | PythonRuntime check ok")
            #console_status.update(status="[magenta]Provisioning Python WSGI App", spinner="earth")
            try:
                self.collected_project_metadata["django_check_messages"] = \
                        self.django_check(app_tmp_dir=app_tmp_dir)
            except DjangoCheckError:
                self.check_cleanup(app_tmp_dir)
                raise PythonRuntimeDjangoCheckError("django check command failed")
            try:
                self.collected_project_metadata["django_settings"] = \
                        self.django_diffsettings(app_tmp_dir=app_tmp_dir)
            except DjangoDiffSettingsError:
                self.check_cleanup(app_tmp_dir)
                raise PythonRuntimeDjangoCheckError("django diffsettings command failed.")
            return True
        return False

    def django_check(
            self,
            cmd_env: dict | None = None,
            app_tmp_dir: Path | None = None,
        ) -> DjangoCheckMessages:
        chdir = app_tmp_dir or self.app_root_dir
        logger.info(f"[pikesquares] run django check in {str(chdir)}")
        dj_msgs = DjangoCheckMessages()

        # DJANGO_SETTINGS_MODULE=mysite.settings
        # uv run python -c "from django.conf import settings ; print(settings.WSGI_APPLICATION)"
        cmd_args = ["run", "manage.py", "check"]
        try:
            retcode, stdout, stderr = self.uv_cmd(
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
                                message="".join(msg.split(")")[1:],
                            ).strip()
                        )
                    )
                return dj_msgs
            else:
                raise DjangoCheckError(f"[pikesquares] UvExecError: unable to run django check in {str(chdir)}") from None

        logger.info(
            f"django check completed. no errors.: {retcode=} {stdout=} {stderr=}"
        )
        return dj_msgs

    def django_diffsettings(
        self,
        cmd_env: dict | None = None,
        app_tmp_dir: Path | None = None,
        ) -> DjangoSettings:
        logger.info("[pikesquares] django diffsettings")
        cmd_args = ["run", "manage.py", "diffsettings"]
        chdir = app_tmp_dir or self.app_root_dir
        try:
            retcode, stdout, stderr = self.uv_cmd(
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
            raise DjangoDiffSettingsError(
                f"[pikesquares] UvExecError: unable to run django diffsettings in {chdir}"
            )

    def get_app(
        self,
        conf: AppConfig,
        db: TinyDB,
        name: str,
        service_id: str,
        app_project,
        venv: Path,
        routers: list[Router]
        ) -> DjangoWsgiApp:

        if "django_settings" not in self.collected_project_metadata:
            raise DjangoSettingsError("unable to detect django settings")

        django_settings = self.collected_project_metadata.\
                get("django_settings")

        logger.debug(django_settings.model_dump())

        django_check_messages = self.collected_project_metadata.\
                get("django_check_messages", [])

        for msg in django_check_messages.messages:
            logger.debug(f"{msg.id=}")
            logger.debug(f"{msg.message=}")

        wsgi_parts = django_settings.wsgi_application.split(".")[:-1]
        wsgi_file = self.app_root_dir / Path("/".join(wsgi_parts) + ".py")
        app_options = {
            "root_dir": self.app_root_dir,
            "project_id": app_project.service_id,
            "wsgi_file": wsgi_file,
            "wsgi_module": django_settings.wsgi_application.split(".")[-1],
            "pyvenv_dir": str(venv),
            "routers": routers,
            "workers": 3,
        }
        return DjangoWsgiApp(
            conf=conf,
            db=db,
            service_id=service_id,
            name=name,
            build_config_on_init=True,
            app_options=WsgiAppOptions(**app_options),
        )

