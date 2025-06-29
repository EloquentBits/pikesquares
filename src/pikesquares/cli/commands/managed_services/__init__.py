from typing import Annotated
import traceback

import structlog
import questionary
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
            machine_id = await AttachedDaemon.read_machine_id()
            device = await uow.devices.get_by_machine_id(machine_id)
            if not device:
                raise RuntimeError("no device found")

            projects = await device.awaitable_attrs.projects
            if not len(await device.awaitable_attrs.projects):
                console.success("Appears there have been no projects created.")
                raise typer.Exit(0) from None

            try:
                if not len(projects):
                    return
                elif len(projects) == 1:
                    return projects[0]

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
                console.info("selection cancelled.")
                raise typer.Exit(0) from None

            if not selected_project_id:
                console.warning("no project selected")
                return

            project = await uow.projects.get_by_id(selected_project_id)
            if not project:
                console.warning(f"Unable to locate project by id {selected_project_id}")
                return

            attached_daemons = await project.awaitable_attrs.attached_daemons
            if not attached_daemons:
                console.success(f"Appears there are no managed services in project {project.name} [{project.service_id}].")
                raise typer.Exit(0) from None

            async def check_vassal_state(daemon: AttachedDaemon) -> str:
                try:
                    if bool(await daemon.read_stats()):
                        return "running"
                except tenacity.RetryError:
                    pass
                return "stopped"

            #plugin_manager = await services.aget(context, PluginManager)
            for attached_daemon in attached_daemons:
                """
                daemon_conf = conf.attached_daemon_plugins.get(attached_daemon.name)
                if not daemon_conf:
                    logger.error(f"unable to lookup attached daemon plugin {attached_daemon.name}")
                    raise typer.Exit(1) from None
                plugin_class = daemon_conf.get("class")
                if not plugin_class:
                    logger.error(f"unable to lookup {attached_daemon.name} class in config")
                    continue

                attached_daemon_device = await uow.tuntap_devices.\
                    get_by_linked_service_id(attached_daemon.service_id)

                plugin_instance = plugin_class(
                    daemon_service=attached_daemon,
                    bind_ip=str(attached_daemon_device.ip),
                )
                if attached_daemon_device:
                    plugin_manager.register(plugin_instance)

                """
                vassal_state = "running" #await check_vassal_state(attached_daemon)
                if vassal_state == "running":
                    daemon_ping = True #plugin_manager.hook.ping()
                else:
                    daemon_ping = False
                console.info(
                    f"{attached_daemon.name} - {attached_daemon.service_id} - Vassal: {vassal_state} - Daemon Ping: {'Up' if daemon_ping else 'Down'}"
                )

                #plugin_manager.unregister(plugin_instance)

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
    plugin_manager = await services.aget(context, pluggy.PluginManager)
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
            for attached_daemon in attached_daemons:
                try:
                    daemon_conf = conf.attached_daemon_plugins.get(attached_daemon.name)
                    if not daemon_conf:
                        logger.error(f"unable to lookup attached daemon plugin {attached_daemon.name}")
                        raise typer.Exit(1) from None
                    plugin_class = daemon_conf.get("class")
                    if not plugin_class:
                        logger.error(f"unable to lookup {attached_daemon.name} class in config")
                        continue

                    attached_daemon_device = await uow.tuntap_devices.\
                        get_by_linked_service_id(attached_daemon.service_id)

                    plugin_instance = plugin_class(
                        daemon_service=attached_daemon,
                        bind_ip=str(attached_daemon_device.ip),
                    )
                    if attached_daemon_device:
                        plugin_manager.register(plugin_instance)
                    if await attached_daemon_up(
                        attached_daemon,
                        plugin_manager,
                        uow,
                        create_data_dir=daemon_conf.get("create_data_dir"),
                        ):
                        console.info(f"started managed service {attached_daemon.name} [{attached_daemon.service_id}]")
                    plugin_manager.unregister(plugin_instance)
                except Exception as exc:
                    logger.error(exc)
                    console.error(
                        f"failed to stop managed service {attached_daemon.name} [{attached_daemon.service_id}]"
                    )

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
            for attached_daemon in attached_daemons:
                try:

                    daemon_conf = conf.attached_daemon_plugins.get(attached_daemon.name)
                    if not daemon_conf:
                        logger.error(f"unable to lookup attached daemon plugin {attached_daemon.name}")
                        raise typer.Exit(1) from None
                    plugin_class = daemon_conf.get("class")
                    if not plugin_class:
                        logger.error(f"unable to lookup {attached_daemon.name} class in config")
                        continue

                    attached_daemon_device = await uow.tuntap_devices.\
                        get_by_linked_service_id(attached_daemon.service_id)

                    plugin_instance = plugin_class(
                        daemon_service=attached_daemon,
                        bind_ip=str(attached_daemon_device.ip),
                    )
                    if attached_daemon_device:
                        plugin_manager.register(plugin_instance)

                    if await attached_daemon_down(
                        attached_daemon,
                        plugin_manager,
                        uow,
                    ):
                        console.info(f"stopped managed service {attached_daemon.name} {attached_daemon.service_id}")
                    plugin_manager.unregister(plugin_instance)
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
