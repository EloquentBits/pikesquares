from pathlib import Path
from typing import Optional
import traceback

import randomname
import structlog

import typer
import questionary
import tenacity

# from pikesquares import (
#    get_service_status,
# )
from pikesquares import services
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.service_layer.handlers.project import (
    provision_project,
    project_up,
    project_delete,
    project_down,
)
from pikesquares.service_layer.handlers.routers import http_router_up
from pikesquares.services.data import DeviceStats
from pikesquares.conf import AppConfig, AppConfigError
from pikesquares.domain.base import ServiceBase
from pikesquares.domain.process_compose import ProcessCompose
from pikesquares.cli.cli import run_async
from pikesquares.cli.console import console
from pikesquares.cli.validators import ServiceNameValidator
#, NameValidator



logger = structlog.get_logger()


# ALIASES = ("proj", "prj")
# HELP = f"""
#    Projects related commands.\n
#    Aliases: [i]{', '.join(ALIASES)}[/i]
# """

# proj_cmd = typer.Typer(no_args_is_help=True, rich_markup_mode="rich", name="projects", help=HELP)
# for alias in ALIASES:
#    app.add_typer(proj_cmd, name=alias, help=HELP, hidden=True)

app = typer.Typer()


@app.command(short_help="Create new project.\nAliases:[i] new")
@app.command(
    # "new", hidden=True
)
@run_async
async def create(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Argument("", help="New project name"),
):
    """
    Create new project in environment

    Aliases: [i] create, new
    """
    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    conf = await services.aget(context, AppConfig)
    uow = await services.aget(context, UnitOfWork)

    machine_id = await ServiceBase.read_machine_id()
    device = await uow.devices.get_by_machine_id(machine_id)

    #answers = questionary.form(
    #    first = questionary.confirm("Would you like the next question?", default=True),
    #    second = questionary.select("Select item", choices=["item1", "item2", "item3"])
    #).ask()

    project_src = await questionary.select(
        "Provision project from: ",
        choices=["Preconfigured template", "Empty project"],
        style=custom_style,
    ).ask_async()
    if not project_src:
        raise typer.Exit(0)

    #questionary.print(
    #    "Hello World ",
        #style="bold italic fg:darkred"
    #)

    if project_src == "Empty project":
        name = await questionary.text(
            "Choose a name for your project: ",
            default=randomname.get_name().lower(),
            style=custom_style,
            #validate=NameValidator,
        ).ask_async()
        if not name:
            raise typer.Exit(0)

        try:
            selected_services = await questionary.checkbox(
                "Provision services: ",
                choices=[
                    questionary.Choice("HTTP Router", value="http-router", checked=False),
                    questionary.Choice("TunTap Router", value="tuntap-router", checked=True),
                    questionary.Choice("Forkpty Router", value="forkpty-router", disabled="coming soon"),
                    questionary.Separator(),
                    questionary.Choice("ZMQ Monitor",  value="zmq-monitor",  checked=True),
                    questionary.Choice("DIR Monitor", value="dir-monitor", disabled="coming soon"),
                ],
                style=custom_style,
            ).unsafe_ask_async()
        except KeyboardInterrupt:
            console.info("selection cancelled.")
            raise typer.Exit(0)

        process_compose = await services.aget(context, ProcessCompose)
        questionary.print(f"Provisioning project {name}")
        async with uow:
            try:
                project = await provision_project(
                    name,
                    device,
                    uow,
                    selected_services=selected_services
                )
                #questionary.print(f"Provisioned project {name}")
                console.success(f":heavy_check_mark:     Provisioned project {name}")
            except Exception as exc:
                logger.exception(exc)
                console.warning(f"Unable to provision project {name}")
                await uow.rollback()
                raise typer.Exit(1) from None
            else:
                await uow.commit()

            if await questionary.confirm("Launch Project?").ask_async():
                try:
                    if not await project_up(project):
                        console.error(f"Unable to launch project {project.name}")
                        raise typer.Exit(1)
                    if 0:
                        try:
                            stats = await project.read_stats()
                        except tenacity.RetryError:
                            console.error(f"Unable to read stats {project.name}")
                            raise typer.Exit(1)
                #await process_compose.add_tail_log_process(project.name, project.log_file)
                except Exception as exc:
                    logger.exception(exc)
                    console.print(traceback.format_exc())
                    console.warning(f"Unable to launch project {name}")
                    raise typer.Exit(1) from None

                console.success(f":heavy_check_mark:     Launched project {name}")

            project_http_routers = await project.awaitable_attrs.http_routers
            for http_router in project_http_routers:
                try:
                    http_router_up_result = await http_router_up(uow, http_router)
                    if http_router_up_result:
                        console.success(":heavy_check_mark:     Launching http router.. Done!")
                        console.success(":heavy_check_mark:     Launching http router subscription server.. Done!")
                        #await process_compose.add_tail_log_process(http_router.service_id, http_router.log_file)
                except Exception as exc:
                    logger.exception(exc)
                    console.print(traceback.format_exc())
                    console.warning(f"Unable to launch http router {http_router}")
                    raise typer.Exit(1) from None

    if 0:
        name = project_name or console.ask(
            "Please submit a project name or hit the Enter key to proceed with  a random value",
            default=randomname.get_name(),
            validators=[ServiceNameValidator],
        )
        project = await provision_project(name, context, uow)
        if project:
            console.success(f":heavy_check_mark:     Project '{project.name}' was successfully created!")
            device = context.get("device")
            if not device:
                raise AppConfigError("no device found in context")

            device_zmq_monitor = await uow.zmq_monitors.get_by_device_id(device.id)
            await device_zmq_monitor.create_or_restart_instance(f"{project.service_id}.ini", project)
            console.success(f":heavy_check_mark:     Launching project [{project.name}]. Done!")
        else:
            console.warning("Failed to create a Project")


@app.command(short_help="Stop Project Service.\nAliases:[s] stop")
@app.command(
    # "stop", hidden=True
)
@run_async
async def stop(
    ctx: typer.Context,
    name: str | None = typer.Argument("", help="Project name"),
):
    """
    Stop project service

    Aliases: [s] stop
    """
    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    uow = await services.aget(context, UnitOfWork)

    machine_id = await ServiceBase.read_machine_id()
    device = await uow.devices.get_by_machine_id(machine_id)

    if not len(await device.awaitable_attrs.projects):
        console.success("Appears there have been no projects created yet.")
        raise typer.Exit(0)

    async with uow:
        try:
            selected_projects = await questionary.checkbox(
                "Select a project to stop: ",
                choices=[
                    questionary.Choice(
                        project.name, value=project.id, checked=True
                    ) for project in await device.awaitable_attrs.projects 
                ],
                style=custom_style,
            ).unsafe_ask_async()
        except KeyboardInterrupt:
            console.info("selection cancelled.")
            raise typer.Exit(0) from None

        for project_id in selected_projects:
            if not project_id:
                continue

            for project in filter(
                    lambda proj: proj.id == project_id,
                    await device.awaitable_attrs.projects
                ):

                if await project_down(project, uow):
                    console.info(f"stopped project {project.name}")
                else:
                    console.warning(f"unable to stop project {project.name}")
                    continue


@app.command(
    "projects",
    rich_help_panel="Show",
    short_help="Show all projects in specific environment.\nAliases:[i] projects, projects list",
)
# @app.command("proj", rich_help_panel="Show", hidden=True)
@app.command("list")
@run_async
async def list_(ctx: typer.Context, show_id: bool = False):
    """
    Show all projects on current device

    Aliases:[i] projects, projects list
    """
    context = ctx.ensure_object(dict)
    conf = await services.aget(context, AppConfig)
    uow = await services.aget(context, UnitOfWork)

    machine_id = await ServiceBase.read_machine_id()
    async with uow:
        device = await uow.devices.get_by_machine_id(machine_id)
        if not device:
            console.warning("unable to lookup device")
            raise typer.Exit(0)

        if not len(await device.awaitable_attrs.projects):
            console.success("Appears there have been no projects created yet.")
            raise typer.Exit(0)

        #device_zmq_monitor = await uow.zmq_monitors.get_by_device_id(device.id)
        #zmq_monitor = await uow.zmq_monitors.get_by_project_id(project.id)

        projects = await uow.projects.list()
        if not len(projects):
            console.warning("No projects were initialized, nothing to show!")
            raise typer.Exit()

        projects_out = []
        try:
            stats = await device.read_stats()
            device_stats = DeviceStats(**stats)
        except tenacity.RetryError:
            console.error(f"Unable to read stats for device [{device.machine_id}]")
            raise typer.Exit(0) from None

        if not device_stats:
            console.warning("unable to lookup device stats")
            raise typer.Exit(0) from None

        for project in projects:
            try:
                vassal_stats = next(
                    filter(lambda v: v.id.split(".ini")[0], device_stats.vassals)
                )
                projects_out.append(
                    {
                        "name": project.name,
                        "status": "running" if vassal_stats else "stopped",
                        "id": project.service_id,
                    }
                )
            except StopIteration:
                continue

        console.print_response(projects_out, title=f"Projects count: {len(projects)}", show_id=show_id)


@app.command("logs")
def logs(ctx: typer.Context, project_id: Optional[str] = typer.Argument("")):
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    if not project_id:
        available_projects = {p.get("name"): p.get("cuid") for p in obj['projects']()}
        project_name = console.choose("Choose project which you want to view logs:", choices=available_projects)
        project_id = available_projects.get(project_name)

    status = get_service_status(f"{project_id}-emperor", conf)

    project_log_file = Path(f"{conf.log_dir}/{project_id}.log")
    if project_log_file.exists() and project_log_file.is_file():
        console.pager(
            project_log_file.read_text(), status_bar_format=f"{project_log_file.resolve()} (status: {status})"
        )
    else:
        nonsole.error(
            f"Error:\nLog file {project_log_file} not exists!", hint=f"Check the device log file for possible errors"
        )


@app.command(short_help="Delete existing project by name or id\nAliases:[i] delete, rm")
@app.command("rm", hidden=True)
@run_async
async def delete(
    ctx: typer.Context,
    project_name: Optional[str] = typer.Argument("", help="Name of project to remove"),
):
    """
    Delete existing project by name or id

    Aliases:[i] delete, rm
    """
    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")
    uow = await services.aget(context, UnitOfWork)

    machine_id = await ServiceBase.read_machine_id()
    device = await uow.devices.get_by_machine_id(machine_id)

    if not len(await device.awaitable_attrs.projects):
        console.success("Appears there have been no projects created yet.")
        raise typer.Exit(0)

    async with uow:
        try:
            selected_projects = await questionary.checkbox(
                "Existing projects: ",
                choices=[
                    questionary.Choice(
                        f"{project.name} [{project.service_id}]",
                        value=project.id,
                        checked=True,
                    ) for project in await device.awaitable_attrs.projects 
                ],
                style=custom_style,
            ).unsafe_ask_async()
        except KeyboardInterrupt:
            console.info("selection cancelled.")
            raise typer.Exit(0) from None

        for project_id in selected_projects:
            if not project_id:
                continue

            for project in filter(
                    lambda proj: proj.id == project_id,
                    await device.awaitable_attrs.projects
                ):

                if await project_down(project, uow):
                    console.info(f"stopped project {project.name}")
                else:
                    console.warning(f"unable to stop project {project.name}")
                    continue

                try:
                    await project_delete(project, uow)
                except Exception as exc:
                    logger.exception(exc)
                    console.error(f"Unable to delete project {project.name}")
                    await uow.rollback()
                    continue
                else:
                    await uow.commit()

    # projects_choices = {
    #    k.get('name'): (k.get('cuid'), k.get('path'))
    #    for k in device_db.search(where("type") == 'Project')
    # }
    # if not projects_choices:
    #    console.warning("No projects were initialized, nothing to delete!")
    #    return

    # selected_project_name = project_name
    # if not selected_project_name:
    #    selected_project_name = console.choose(
    #        "Which project you want to delete?",
    #        choices=projects_choices,
    #    )

    # rm project sources
    # selected_project_cuid, selected_project_path = projects_choices.get(selected_project_name)
    # if Path(selected_project_path).exists() and console.confirm(f"Are you sure you want to delete: {selected_project_path}"):
    #    shutil.rmtree(selected_project_path)

    # rm project configs
    # selected_project_config_path = Path(conf.CONFIG_DIR) / selected_project_cuid
    # selected_project_config_path.with_suffix('.json').unlink(missing_ok=True)
    # if Path(selected_project_config_path).exists():
    #    shutil.rmtree(str(selected_project_config_path.resolve()))

    # rm project runtimes
    # for file in Path(conf.RUN_DIR).iterdir():
    #    if selected_project_cuid in str(file.resolve()):
    #        file.unlink(missing_ok=True)

    # rm project from db
    # device_db.remove(where('cuid') == selected_project_cuid)

    # console.success(f"Removed project '{selected_project_name}'!")


# @app.command(short_help="Start project.\nAliases:[i] run")
# @app.command("run", hidden=True)
# def start(
#    ctx: typer.Context,
#    project_name: Optional[str] = typer.Argument("", help="Project to start"),
# ):
#    """
#    Start project.

#    Aliases: [i] start, run
#    """
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    device_db = obj['device']

# for project_doc in db.table('projects'):
#    project_up(conf, project_doc.service_id)

#    if not project_name:
#        available_projects = {p.get('name'): p.get('cuid') for p in obj['projects']()}
#        if not available_projects:
#            console.warning("Create at least one project first, before starting it!")
#            return
#        project_name = console.choose("Select project you want to start", choices=available_projects)

#    project_ent = device_db.get(where('name') == project_name)

#    project_id = project_ent.get('cuid')
#    project_type = project_ent.get('type')
#    if project_type != "Project":
#        console.error(
#            "You've entered app name instead of project name!",
#            example=f"vc apps start '{project_name}'"
#        )
#        return

# project = HandlerFactory.make_handler(project_type)(
#    service_id=project_id,
#    conf=conf,
# )
# if project.is_started():
#    console.info(f"Project '{project_name}' is already started!")
#    return

# project.prepare_service_config()
# project.connect()
# project.start()
# console.success(f"Project '{project_name}' was successfully started!")


# @app.command(short_help="Stop project.\nAliases:[i] down")
# @app.command("down", hidden=True)
# def stop(
#    ctx: typer.Context,
#    project_name: Optional[str] = typer.Argument("", help="Project to stop"),
# ):
#    """
#    Stop project.

#    Aliases: [i] stop, down
#    """
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    device_db = obj['device']

#    project_ent = device_db.search(where('name') == project_name)
#    if not project_ent:
#        console.error(f"Project with name '{project_name}' does not exists!")
#        return
#    else:
#        project_ent = project_ent[0]

#    project_id = project_ent.get('cuid')
#    project_type = project_ent.get('type')
#    if project_type != "Project":
#        console.error(
#            "You've entered app name instead of project name!",
#            example=f"vc apps stop '{project_name}'"
#        )
#        return

# project = HandlerFactory.make_handler(project_type)(
#    service_id=project_id,
#    conf=conf,
# )
# if not project.is_started():
#    console.info(f"Project '{project_name}' is not started!")
#    return

# project.connect()
# project.stop()
# console.success(f"Project '{project_name}' was successfully stopped!")

# app.add_typer(app)

if __name__ == "__main__":
    app()
