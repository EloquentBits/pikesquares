import sys
import shutil
import traceback
import re
import os
from pathlib import Path

import pydantic
from plumbum import ProcessExecutionError

from .wsgi import WsgiApp
from .exceptions import (
    UvCommandExecutionError,
    DjangoCheckError,
    DjangoDiffSettingsError,
)


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


class PythonRuntimeDjangoMixin:

    PY_DJANGO_FILES: set[str] = set({
        "urls.py",
        "wsgi.py",
        "settings.py",
        "manage.py",
    })

    def is_django(self, app_tmp_dir: Path | None = None) -> bool:
        all_files = []
        for filename in self.PY_DJANGO_FILES:
            all_django_files = Path(app_tmp_dir or self.app_root_dir).glob(f"**/{filename}")
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

    def django_check(
            self,
            cmd_env: dict | None = None,
            app_tmp_dir: Path | None = None,
        ):
        chdir = app_tmp_dir or self.app_root_dir
        print(f"[pikesquares] run django check in {str(chdir)}")

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
                # retcode=0
                # stdout='System check identified no issues (0 silenced).\n'
                # stderr='warning: `VIRTUAL_ENV=/home/pk/dev/eqb/pikesquares/.venv` does not match the project environment path `.venv` and will be ignored\n'
                # stderr "System check identified some issues:\n\nWARNINGS:\n?: (staticfiles.W004) The directory '/tmp/pre_1d82tc06_suf/static' in the STATICFILES_DIRS setting does not exist.\n\nSystem check identified 1 issue (0 silenced).\n
                return True
        except ProcessExecutionError as plumbum_pe_err:

            if "hc.api.W002" in plumbum_pe_err.stderr:
                print("hc.api.W002")
                pass
            elif "caches.E001" in plumbum_pe_err.stderr:
                print("caches.E001")
                pass
            elif "staticfiles.W004" in plumbum_pe_err.stderr:
                # The directory '/tmp/pre_icugrao4_suf/static' in the STATICFILES_DIRS
                # create static dir
                match = re.search(r"/tmp/pikesquares_[a-zA-Z0-9]+_py_app/static", plumbum_pe_err.stderr)
                if match:
                    print(f"[pikesquares] creating staticfiles directory {match.group()}")
                    try:
                        Path(match.group()).mkdir()
                    except:
                        traceback.format_exc()
                        raise DjangoCheckError(f"Django check: unable to create staticfiles directory {match.group()}")
                    else:
                        print("[pikesquares] re-running Django check")
                        self.django_check(app_tmp_dir or self.app_root_dir)
            # else:
            #    raise DjangoCheckError(f"Django check: {plumbum_pe_err.retcode=} {plumbum_pe_err.stdout=} plumbum_pe_errs.stderr=}")
            else:
                raise DjangoCheckError(
                    f"[pikesquares] UvExecError: unable to run django check in {str(chdir)}"
                )
        else:
            print(
                f"django check completed: {plumbum_pe_err.retcode=} {plumbum_pe_err.stdout=} {plumbum_pe_errs.stderr=}"
            )

    def django_diffsettings(
        self,
        cmd_env: dict | None = None,
        app_tmp_dir: Path | None = None,
        ):
        print("[pikesquares] django diffsettings")
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
                            print(f"did not find a match for {fld}")

            assert dj_settings
            django_settings = DjangoSettings(**dj_settings)
            print(django_settings.model_dump())
            return django_settings

        except UvCommandExecutionError:
            raise DjangoDiffSettingsError(
                f"[pikesquares] UvExecError: unable to run django diffsettings in {chdir}"
            )


class DjangoWsgiApp(WsgiApp):
    pass
