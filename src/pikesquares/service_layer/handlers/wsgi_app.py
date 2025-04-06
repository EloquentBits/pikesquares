from pathlib import Path

import structlog

from pikesquares.domain.wsgi_app import WsgiApp
from pikesquares.services.apps.exceptions import DjangoSettingsError
from pikesquares.services.apps.django import PythonRuntimeDjango

logger = structlog.getLogger()


def create_wsgi_app(
    runtime,
    name: str,
    service_id: str,
    app_project,
    venv: Path,
    # routers: list[Router],
) -> WsgiApp:

    if "django_settings" not in runtime.collected_project_metadata:
        raise DjangoSettingsError("unable to detect django settings")

    django_settings = runtime.collected_project_metadata.get("django_settings")
    logger.debug(django_settings.model_dump())

    django_check_messages = runtime.collected_project_metadata.get("django_check_messages", [])

    for msg in django_check_messages.messages:
        logger.debug(f"{msg.id=}")
        logger.debug(f"{msg.message=}")

    wsgi_parts = django_settings.wsgi_application.split(".")[:-1]
    wsgi_file = runtime.app_root_dir / Path("/".join(wsgi_parts) + ".py")
    app_options = {
        "root_dir": runtime.app_root_dir,
        "project_id": app_project.service_id,
        "wsgi_file": wsgi_file,
        "wsgi_module": django_settings.wsgi_application.split(".")[-1],
        "pyvenv_dir": str(venv),
        # "routers": routers,
        "workers": 3,
    }
    uwsgi_plugins = []
    # if isinstance(runtime, PythonRuntimeDjango):
    return WsgiApp(
        service_id=service_id,
        name=name,
        uwsgi_plugins=",".join(uwsgi_plugins),
        **app_options,
    )
