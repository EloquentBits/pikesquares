from typing import Annotated
import traceback

import structlog
import typer
from pluggy import PluginManager
import tenacity

from pikesquares import services
from pikesquares.cli.cli import run_async
from pikesquares.cli.console import console
from pikesquares.conf import AppConfig
from pikesquares.domain.managed_services import AttachedDaemon
from pikesquares.service_layer.handlers.attached_daemon import (
    attached_daemon_down,
    attached_daemon_up,
)
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.service_layer.handlers.prompt_utils import (
    prompt_for_project,
    prompt_for_attached_daemons,
)

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


@app.command(short_help="List running managed services \nAliases:[s] list")
@app.command("list")
@run_async
async def list_(ctx: typer.Context):
    """
    List managed services

    Aliases:[l] list
    """
    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    conf = await services.aget(context, AppConfig)
    uow = await services.aget(context, UnitOfWork)
    try:
        async with uow:
            try:
                project = await prompt_for_project(uow, custom_style)
                if not project:
                    console.warning("unable to retrieve list of projects")
                    raise typer.Exit(0) from None
            except KeyboardInterrupt:
                console.info("selection cancelled.")
                raise typer.Exit(0) from None

            attached_daemons = await project.awaitable_attrs.attached_daemons
            if not attached_daemons:
                console.success(f"Appears there are no managed services in project {project.name} [{project.service_id}].")
                raise typer.Exit(0) from None

            async def check_status(daemon: AttachedDaemon) -> str:
                try:
                    if bool(await daemon.read_stats()):
                        return "running"
                except tenacity.RetryError:
                    pass
                return "stopped"

            for daemon in attached_daemons:
                status = await check_status(daemon)
                console.info(f"{daemon.name} - {daemon.service_id} - {status}")

    except Exception as exc:
        logger.error(exc)
        console.error("failed to list managed services")
        raise typer.Exit(1) from None


@app.command(short_help="Start running managed service \nAliases:[s] start")
@run_async
async def start(
    ctx: typer.Context,
    service_name: str | None = typer.Argument("", help="Name of managed service to start"),
):
    """
    Start a stopped Managed service


    Aliases:[s] start
    """
    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    conf = await services.aget(context, AppConfig)
    uow = await services.aget(context, UnitOfWork)
    try:
        async with uow:
            try:
                project = await prompt_for_project(uow, custom_style)
                if not project:
                    console.warning("unable to retrieve project")
                    raise typer.Exit(0) from None
                attached_daemons = await prompt_for_attached_daemons(
                    uow,
                    project,
                    custom_style,
                    is_running=False,
                )
            except KeyboardInterrupt:
                console.info("selection cancelled.")
                raise typer.Exit(0) from None

            if not attached_daemons:
                console.success("Appears there are no stopped managed services in this project.")
                raise typer.Exit(0) from None

            plugin_manager = await services.aget(context, PluginManager)
            for attached_daemon in attached_daemons :
                try:
                    if await attached_daemon_up(
                        attached_daemon,
                        plugin_manager,
                        uow,
                        conf,
                    ):
                        console.info(f"started managed service {attached_daemon.name} [{attached_daemon.service_id}]")
                except Exception as exc:
                    logger.error(exc)
                    console.error("failed to stop managed service {attached_daemon.name} [{attached_daemon.service_id}]")
    except Exception as exc:
        logger.error(exc)
        console.error("failed to stop managed services")
        raise typer.Exit(1) from None

@app.command(short_help="Stop running managed service \nAliases:[s] stop")
@run_async
async def stop(
    ctx: typer.Context,
    service_name: str | None = typer.Argument("", help="Name of managed service to stop"),
):
    """
    Stop a running Managed service


    Aliases:[s] stop
    """
    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    conf = await services.aget(context, AppConfig)
    uow = await services.aget(context, UnitOfWork)

    try:
        async with uow:
            project = await prompt_for_project(uow, custom_style)
            if not project:
                console.warning("unable to retrieve project")
                raise typer.Exit(0) from None

            attached_daemons = await prompt_for_attached_daemons(
                uow,
                project,
                custom_style,
                is_running=True,
                )
            if not attached_daemons:
                console.success("Appears there have been no Managed Services created in this project yet.")
                raise typer.Exit(0) from None

            plugin_manager = await services.aget(context, PluginManager)
            for attached_daemon in attached_daemons :
                try:
                    if await attached_daemon_down(
                        attached_daemon,
                        plugin_manager,
                        uow,
                        conf,
                    ):
                        console.info(f"stopped managed service {attached_daemon.name} {attached_daemon.service_id}")
                except Exception as exc:
                    logger.error(exc)
                    print(traceback.format_exc())
                    console.error(
                        f"failed to stop managed service {attached_daemon.name} [{attached_daemon.service_id}]"
                    )
    except Exception as exc:
        logger.error(exc)
        print(traceback.format_exc())
        console.error("failed to stop managed services")
        raise typer.Exit(1) from None

if __name__ == "__main__":
    app()
