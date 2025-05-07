from pathlib import Path

import structlog
from aiopath import AsyncPath

from pikesquares.domain.wsgi_app import WsgiApp
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.domain.project import Project
from pikesquares.services.apps.exceptions import DjangoSettingsError
from pikesquares.services.apps.python import PythonRuntime
from pikesquares.services.apps.django import PythonRuntimeDjango, DjangoSettings 


logger = structlog.getLogger()


async def create_wsgi_app(
    uow: UnitOfWork,
    runtime: PythonRuntime,
    service_id: str,
    name: str,
    wsgi_file: AsyncPath,
    wsgi_module: str,
    project: Project,
    pyvenv_dir: Path,
    uwsgi_plugins: list[str] | None = None,
    # routers: list[Router],
) -> WsgiApp:

    wsgi_app = WsgiApp(
        service_id=service_id,
        name=name,
        project=project,
        uwsgi_plugins=",".join(uwsgi_plugins) if uwsgi_plugins else "",
        root_dir=str(runtime.app_root_dir),
        wsgi_file=str(wsgi_file),
        wsgi_module=wsgi_module,
        pyvenv_dir=str(pyvenv_dir),
    )
    try:
        await uow.wsgi_apps.add(wsgi_app)
    except Exception as exc:
        raise exc

    return wsgi_app
