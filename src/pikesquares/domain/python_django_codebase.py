from pathlib import Path

import pydantic


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
