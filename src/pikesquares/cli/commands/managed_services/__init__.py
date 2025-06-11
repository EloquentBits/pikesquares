import typer

from typing_extensions import Annotated

import questionary
import structlog
from pluggy import PluginManager

from pikesquares.cli.cli import run_async
from pikesquares import services
from pikesquares.conf import AppConfig, AppConfigError
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.service_layer.handlers.attached_daemon import attached_daemon_down
from pikesquares.domain.base import ServiceBase
from pikesquares.cli.console import console

logger = structlog.getLogger()

app = typer.Typer()

@app.command(short_help="Create new managed service\nAliases: [i] create, new")
@run_async
async def create(
    ctx: typer.Context,
    project: str | None = typer.Option("", "--in", "--in-project",
        help="Name or id of project to add new service to"
    ),
    name: Annotated[str, typer.Option("--name", "-n", help="service name")] = "",
):
    """
    Create new managed service in project

    Aliases: [i] create, new
    """
    obj = ctx.ensure_object(dict)
    custom_style = obj.get("cli-style")


@app.command(short_help="Stop running managed service \nAliases:[s] stop")
@run_async
async def stop(
    ctx: typer.Context,
    service_name: str | None = typer.Argument("", help="Name of managed service to stop"),
):
    """
    Stop a running Managed Service

    Aliases:[s] stop
    """
    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    conf = await services.aget(context, AppConfig)
    uow = await services.aget(context, UnitOfWork)

    machine_id = await ServiceBase.read_machine_id()
    device = await uow.devices.get_by_machine_id(machine_id)
    if not device:
        raise AppConfigError("no device found in context")

    if not len(await device.awaitable_attrs.projects):
        console.success("Appears there have been no projects created yet.")
        raise typer.Exit(0)

    async with uow:
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
        except KeyboardInterrupt:
            raise typer.Exit(0) from None

        if not selected_project_id:
            console.warning("no project selected")
            raise typer.Exit(0)

        project = await uow.projects.get_by_id(selected_project_id)
        if not project:
            console.warning(f"Unable to locate project by id {selected_project_id}")
            raise typer.Exit(0)

        attached_daemons = await project.awaitable_attrs.attached_daemons
        if not attached_daemons:
            console.success("Appears there have been no Managed Services created in this project yet.")
            raise typer.Exit(0) from None


        plugin_manager = await services.aget(context, PluginManager)
        try:
            selected_attached_daemon_ids = await questionary.checkbox(
                "Select running managed services to stop: ",
                choices=[
                    questionary.Choice(
                        attached_daemon.name, value=attached_daemon.id, checked=True
                    ) for attached_daemon in attached_daemons
                ],
                style=custom_style,
            ).unsafe_ask_async()

            for selected_attached_daemon_id in selected_attached_daemon_ids:
                selected_attached_daemon = await uow.attached_daemons.get_by_id(selected_attached_daemon_id)
                if not selected_attached_daemon:
                    console.warning("unable to lookup selected managed service")
                    raise typer.Exit(0) from None

                try:
                    if await attached_daemon_down(
                        project,
                        selected_attached_daemon,
                        plugin_manager,
                        uow,
                        conf,
                    ):
                        console.info(f"stopped managed service {selected_attached_daemon.name}")
                except Exception as exc:
                    logger.error(exc)
                    print(exc)
                    console.error("failed to stop managed services")
                    await uow.rollback()
                    raise typer.Exit(1) from None
                else:
                    await uow.commit()

        except KeyboardInterrupt:
            raise typer.Exit(0) from None



if __name__ == "__main__":
    app()
