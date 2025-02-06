import sys
import shutil
import traceback
import re
import os
from pathlib import Path

import pydantic

from pikesquares.services.apps.wsgi import WsgiApp
from pikesquares.services.apps.uv_utils import (
    UvExecError,
    uv_cmd,
)


PY_DJANGO_FILES = set({
    "urls.py",
    "wsgi.py",
    "settings.py",
    "manage.py",
})


class DjangoCheckError(Exception):
    pass


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


def uv_django_check(app_root_dir: Path, uv_bin: Path):
    print(f"[pikesquares] uv_django_check: {str(app_root_dir)}")
    os.chdir(app_root_dir)
    cmd_env = {}
    cmd_args = ["run", "manage.py", "check"]
    try:
        retcode, stdout, stderr = uv_cmd(uv_bin, cmd_args, cmd_env, app_root_dir)
        if "System check identified no issues" in stdout:
            return True
        elif "hc.api.W002" in stderr:
            pass
        elif "staticfiles.W004" in stderr:
            # The directory '/tmp/pre_icugrao4_suf/static' in the STATICFILES_DIRS
            # create static dir
            match = re.search(r"/tmp/pre_[a-zA-Z0-9]+_suf/static", stderr)
            if match:
                print(f"[pikesquares] creating staticfiles directory {match.group()}")
                try:
                    Path(match.group()).mkdir()
                except:
                    print(traceback.format_exc())
                    raise DjangoCheckError(f"Django check: unable to create staticfiles directory {match.group()}")
                else:
                    print("[pikesquares] re-running Django check")
                    uv_django_check(app_root_dir, uv_bin)
        else:
            raise DjangoCheckError(f"Django check: {retcode=} {stdout=} {stderr=}")

        # retcode=0
        # stdout='System check identified no issues (0 silenced).\n'
        # stderr='warning: `VIRTUAL_ENV=/home/pk/dev/eqb/pikesquares/.venv` does not match the project environment path `.venv` and will be ignored\n'

        # stderr "System check identified some issues:\n\nWARNINGS:\n?: (staticfiles.W004) The directory '/tmp/pre_1d82tc06_suf/static' in the STATICFILES_DIRS setting does not exist.\n\nSystem check identified 1 issue (0 silenced).\n

    except UvExecError:
        print(f"[pikesquares] UvExecError: unable to run django check in {str(app_root_dir)}")
        shutil.rmtree(app_root_dir)
        sys.exit(1)


def uv_django_diffsettings(app_root_dir: Path, uv_bin: Path):
    print(f"[pikesquares] uv_django_diffsettings: {str(app_root_dir)}")

    os.chdir(app_root_dir)
    cmd_env = {}
    cmd_args = ["run", "manage.py", "diffsettings"]
    try:
        retcode, stdout, stderr = uv_cmd(uv_bin, cmd_args, cmd_env, app_root_dir)
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

    except UvExecError:
        print(f"[pikesquares] UvExecError: unable to run django diffsettings in {str(app_root_dir)}")
        shutil.rmtree(app_root_dir)
        sys.exit(1)


def is_django(app_root_dir: Path):

    all_files = []
    for filename in PY_DJANGO_FILES:
        all_files.extend(Path(app_root_dir).glob(f"**/{filename}"))
    for f in all_files:
        print(f)

    return len(all_files)

    # for f in glob(f"{app_temp_dir}/**/*wsgi*.py", recursive=True):
    #    print(f)
    # [f for f in glob("**/settings.py", recursive=True) if not f.startswith("venv/")]
    # for f in glob(f"{app_temp_dir}/**/settings.py", recursive=True):
    #    settings_module_path = Path(f)
    #    print(f"settings module: {(settings_module_path)}")
    #    print(f"settings module: {settings_module_path.relative_to(app_temp_dir)}")
    # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecomproject.settings')


class DjangoWsgiApp(WsgiApp):
    pass
