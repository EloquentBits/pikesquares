import questionary
import typer
import tenacity
import structlog

from pikesquares.cli.console import console
from pikesquares.conf import AppConfigError
from pikesquares.domain.base import ServiceBase
from pikesquares.domain.device import Device
from pikesquares.domain.managed_services import AttachedDaemon
from pikesquares.domain.project import Project
from pikesquares.service_layer.uow import UnitOfWork


logger = structlog.getLogger()


async def prompt_for_project(uow: UnitOfWork, custom_style) -> Project | None:

    machine_id = await ServiceBase.read_machine_id()
    device = await uow.devices.get_by_machine_id(machine_id)
    if not device:
        raise AppConfigError("no device found in context")

    projects = await device.awaitable_attrs.projects
    if not len(projects):
        return
    elif len(projects) == 1:
        return projects[0]
    try:
        selected_project_id = await questionary.select(
            "Select an existing project: ",
            choices=[
                questionary.Choice(
                    project.name, value=project.id
                ) for project in await device.awaitable_attrs.projects
            ],
            style=custom_style,
        ).unsafe_ask_async()
    except KeyboardInterrupt as exc:
        raise exc

    if not selected_project_id:
        console.warning("no project selected")
        return

    project = await uow.projects.get_by_id(selected_project_id)
    if not project:
        console.warning(f"Unable to locate project by id {selected_project_id}")
        return

    return project

async def prompt_for_attached_daemons(
    uow: UnitOfWork,
    project: Project,
    custom_style,
    is_running: bool = True,
    ) -> list[AttachedDaemon] | None:

    daemons = await project.awaitable_attrs.attached_daemons
    if not daemons:
        console.success("Appears there have been no managed services created in this project yet.")
        return

    async def check_status(daemon: AttachedDaemon) -> str:
        try:
            if bool(await daemon.read_stats()):
                return "running"
        except tenacity.RetryError:
            pass
        return "stopped"

    try:
        selected_daemons = []
        choices = []
        for daemon in daemons:
            status = await check_status(daemon)
            logger.info(f"{daemon.name} [{daemon.service_id}] {is_running=} {status=}")
            if (status == "running" and is_running) or \
                (status == "stopped" and not is_running):
                title = f"{daemon.name.capitalize()} [{daemon.service_id}] in {project.name} [{project.service_id}]"
                choices.append(
                    questionary.Choice(title, value=daemon.id, checked=True)
                )
        logger.info(choices)
        if not choices:
            return

        for daemon_id in await questionary.checkbox(
            "Select running managed services to stop: ",
            choices=choices,
            style=custom_style,
        ).unsafe_ask_async():
            daemon = await uow.attached_daemons.get_by_id(daemon_id)
            if daemon:
                selected_daemons.append(daemon)

        return selected_daemons

    except Exception as exc:
        raise exc

