import structlog
from aiopath import AsyncPath
from cuid import cuid

from pikesquares.domain.project import Project
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def create_project(
    name: str,
    context: dict,
    uow: UnitOfWork,
) -> Project | None:

    device = context.get("device")

    uwsgi_plugins = ["emperor_zeromq"]

    project = Project(
        service_id=f"project_{cuid()}",
        name=name,
        device=device,
        uwsgi_plugins=", ".join(uwsgi_plugins),
        data_dir=str(device.data_dir),
        config_dir=str(device.config_dir),
        log_dir=str(device.log_dir),
        run_dir=str(device.run_dir),
    )
    try:
        await uow.projects.add(project)
        await uow.commit()
    except Exception as exc:
        logger.exception(exc)
        await uow.rollback()

    # if project.enable_dir_monitor:
    #    if not await AsyncPath(project.apps_dir).exists():
    #        await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)
    #    uwsgi_config = project.write_uwsgi_config()
    #    logger.debug(f"wrote config to file: {uwsgi_config}")

    return project
