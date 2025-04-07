from pathlib import Path

import structlog

from pikesquares.domain.wsgi_app import WsgiApp
from pikesquares.domain.project import Project
from pikesquares.services.apps.exceptions import DjangoSettingsError
from pikesquares.services.apps.python import PythonRuntime


logger = structlog.getLogger()


def create_wsgi_app(
    runtime: PythonRuntime,
    name: str,
    service_id: str,
    project: Project,
    pyvenv_dir: Path,
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
    uwsgi_plugins = []
    # if isinstance(runtime, PythonRuntimeDjango):
    return WsgiApp(
        service_id=service_id,
        name=name,
        project=project,
        uwsgi_plugins=",".join(uwsgi_plugins),
        root_dir=str(runtime.app_root_dir),
        wsgi_file=str(wsgi_file),
        wsgi_module=django_settings.wsgi_application.split(".")[-1],
        pyvenv_dir=str(pyvenv_dir),
    )
