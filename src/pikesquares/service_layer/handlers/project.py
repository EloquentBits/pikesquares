import structlog
from aiopath import AsyncPath
from cuid import cuid

from pikesquares.domain.device import Device
from pikesquares.domain.project import Project
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def get_or_create_project(
    name: str,
    device: Device,
    uow: UnitOfWork,
    create_kwargs: dict,
) -> Project:

    project = await uow.projects.get_by_name(name)

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
        await uow.commit()
        logger.debug(f"Created {project} ")
    else:
        logger.debug(f"Using existing sandbox project {project}")

    if project.enable_dir_monitor:
        if not await AsyncPath(project.apps_dir).exists():
            await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)

        uwsgi_config = project.write_uwsgi_config()
        logger.debug(f"wrote config to file: {uwsgi_config}")

    return project
