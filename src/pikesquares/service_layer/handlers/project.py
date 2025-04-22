import structlog
from aiopath import AsyncPath
from cuid import cuid

from pikesquares import services
from pikesquares.domain.device import Device
from pikesquares.domain.project import Project
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.service_layer.handlers.monitors import get_or_create_zmq_monitor

logger = structlog.getLogger()


async def get_or_create_project(
    name: str,
    context: dict,
    create_kwargs: dict,
) -> tuple[Project, bool]:

    uow = await services.aget(context, UnitOfWork)
    device = context.get("device")

    project = await uow.projects.get_by_name(name)
    project_created = not project

    if not project:
        uwsgi_plugins = ["emperor_zeromq"]

        project = Project(
            service_id=f"project_{cuid()}",
            name=name,
            device=device,
            uwsgi_plugins=", ".join(uwsgi_plugins),
            **create_kwargs,
        )
        await uow.projects.add(project)
        logger.debug(f"Created PROJECT {project} ")

        zmq_monitor = await get_or_create_zmq_monitor(
            uow,
            project=project,
        )
        logger.debug(f"Created ZMQ_MONITOR for PROJECT {zmq_monitor}")
    else:
        logger.debug(f"Using existing project {project}")

    # if project.enable_dir_monitor:
    #    if not await AsyncPath(project.apps_dir).exists():
    #        await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)
    #    uwsgi_config = project.write_uwsgi_config()
    #    logger.debug(f"wrote config to file: {uwsgi_config}")

    return project, project_created
