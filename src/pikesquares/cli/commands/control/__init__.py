import asyncio
import os

import apluggy as pluggy
import questionary
import structlog
import tenacity
import typer
from aiopath import AsyncPath
from plumbum import ProcessExecutionError

from pikesquares import services
from pikesquares.cli.console import console
from pikesquares.cli.decorator import run_async
from pikesquares.conf import AppConfig
from pikesquares.domain.base import ServiceBase
from pikesquares.domain.process_compose import (
    PCAPIUnavailableError,
    ProcessCompose,
    ServiceUnavailableError,
)
from pikesquares.service_layer.handlers.attached_daemon import (
    attached_daemon_up,
    provision_attached_daemon,
)
from pikesquares.service_layer.handlers.project import project_up
from pikesquares.service_layer.handlers.prompt_utils import (
    prompt_for_launch_service,
    prompt_for_project,
)
from pikesquares.service_layer.handlers.routers import http_router_up

# from pikesquares.cli.commands.control import app
from pikesquares.service_layer.handlers.runtimes import provision_app_codebase, provision_python_app_runtime
from pikesquares.service_layer.handlers.wsgi_app import provision_wsgi_app, wsgi_app_up
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.get_logger()

app = typer.Typer()


@app.command(rich_help_panel="Control", short_help="Launch the PikeSquares Server (if stopped)")
@run_async
async def up(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """Launch PikeSquares Server"""

    logger.info("running - pikesquares up")

    context = ctx.ensure_object(dict)

    conf = await services.aget(context, AppConfig)
    if not context["run_foreground"]:
        process_compose = await services.aget(context, ProcessCompose)

        # if conf and not conf.pyapps_dir.exists():
        #    logger.error(f"python apps directory @ {conf.pyapps_dir} is not available")
        #    raise typer.Exit(code=1) from None

        # if conf and not conf.attached_daemons_dir.exists():
        #    logger.error(f"attached daemons directory @ {conf.attached_daemons_dir} is not avai#lable")
        #    raise typer.Exit(code=1) from None

        try:
            _ = await process_compose.ping_api("device")
            logger.info("process-compose is already running. not bringing it up now.")
        except PCAPIUnavailableError:
            logger.info("bringing up process-compose")
            up_result = await process_compose.up()
            if not up_result:
                raise typer.Exit(code=0) from None

        #######################
        # process-compose processes
        #    caddy, dnsmasq, device, api
        try:
            for name, process, messages in zip(
                process_compose.config.processes.keys(),
                process_compose.config.processes.values(),
                process_compose.config.custom_messages.values(),
                strict=True,
            ):
                try:
                    console.success(f"{messages.title_start} {process.description}")
                    process_stats = await process_compose.ping_api(name)
                    if process_stats.is_running and process_stats.status == "Running":
                        console.success(f":heavy_check_mark:     {process.description}... Launched!")
                    else:
                        console.warning(f":heavy_exclamation_mark:     {process.description} unable to launch.")
                except PCAPIUnavailableError:
                    await asyncio.sleep(1)
                    continue
        except (StopIteration, IndexError):
            pass

    #######################
    # emperor zeromq monitors
    uow = await services.aget(context, UnitOfWork)
    machine_id = ServiceBase.read_machine_id()
    device = uow.devices.get_by_machine_id(machine_id)
    if not device:
        console.error(f"cli up: unable to locate device by machine id {machine_id}")
        raise typer.Exit(code=0) from None

    with uow:
        projects = device.projects
        for project in projects:
            try:
                if await project_up(project) or not project.read_stats():
                    console.success(f":heavy_check_mark:     Launched project [{project.name}]. Done!")
                    # await process_compose.add_tail_log_process(project.name, project.log_file)
            except tenacity.RetryError:
                console.warning(f"Project {project.name} has not launched. Giving up.")
                continue
            except Exception as exc:
                logger.exception(exc)
                console.warning(f"Project {project.name} has not launched. Giving up.")
                continue

            project_http_routers = project.http_routers
            for http_router in project_http_routers:
                http_router_up_result = await http_router_up(uow, http_router)
                if http_router_up_result:
                    console.success(":heavy_check_mark:     Launching http router.. Done!")
                    console.success(":heavy_check_mark:     Launching http router subscription server.. Done!")
                    # await process_compose.add_tail_log_process(http_router.service_id, http_router.log_file)

    console.success()
    console.success("PikeSquares API is available at: http://127.0.0.1:9000")
    console.success()
    console.success("Next steps: cd to your project directory and run `pikesquares init`")
    console.success()
    console.success("🚀 PikeSquares Server is up and running. 🚀")


@app.command(rich_help_panel="Control", short_help="Stop the PikeSquares Server (if running)")
@run_async
async def down(
    ctx: typer.Context,
):
    """Stop the PikeSquares Server"""

    context = ctx.ensure_object(dict)
    pc = await services.aget(context, ProcessCompose)
    try:
        retcode, stdout, stderr = await pc.down()
        if retcode != 0:
            console.log(retcode, stdout, stderr)
            raise typer.Exit(code=1) from None
        elif retcode == 0:
            console.success("🚀 PikeSquares Server has been shut down.")
    except ProcessExecutionError as process_exec_error:
        console.error(process_exec_error)
        console.error("PikeSquares Server was unable to shut down.")
        raise typer.Exit(code=1) from None
    except PCAPIUnavailableError:
        console.info("🚀 PikeSquares Server is not running at the moment.")
        raise typer.Exit(code=0) from None

    # try:
    #    pc.ping()
    #    console.info("Shutting down PikeSquares Server.")
    #    pc.down()
    # except process_compose.PCAPIUnavailableError:
    #    pass
    # except process_compose.PCDeviceUnavailableError:
    #    pass  # device.up()


@app.command(rich_help_panel="Control", short_help="Reset device")
def reset(
    ctx: typer.Context,
    shutdown: str | None = typer.Option("", "--shutdown", help="Shutdown PikeSquares server after reset."),
):
    """Reset PikeSquares Installation"""

    is_root: bool = os.getuid() == 0
    if not is_root:
        console.info("Please attempt to reset the installation as root user.")
        raise typer.Exit()

    if not questionary.confirm("Reset PikeSquares Installation?").ask():
        raise typer.Exit()

    context = ctx.ensure_object(dict)
    device = context.get("device")
    if not device:
        raise typer.Exit()

    if all(
        [
            device.get_service_status() == "running",
            shutdown or questionary.confirm("Shutdown PikeSquares Server").ask(),
        ]
    ):
        # device.stop()
        # down(ctx)
        pass

    if questionary.confirm("Drop db tables?").ask():
        # device.drop_db_tables()
        console.info("dropped db")

    if questionary.confirm("Delete all configs and logs?").ask():
        # device.delete_configs()
        console.info("deleted configs and logs")


@app.command(rich_help_panel="Control", short_help="Nuke installation")
def uninstall(ctx: typer.Context, dry_run: bool = typer.Option(False, help="Uninstall dry run")):
    """Delete the entire PikeSquares installation"""

    context = ctx.ensure_object(dict)
    # device= services.HandlerFactory.make_handler("Device")(services.Device(service_id="device"))
    # device.uninstall(dry_run=dry_run)
    console.info("PikeSquares has been uninstalled.")


# @app.command(rich_help_panel="Control", short_help="Write to master fifo")
# def write_to_master_fifo(
#    ctx: typer.Context,
#    service_id: Annotated[str, typer.Option("--service-id", "-s", help="Service ID to send the command to")],
#    command: Annotated[str, typer.Option("--command", "-c", help="Command to send master fifo.")],
# ):
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    service_id = service_id or "device"
#    fifo_file = Path(conf.RUN_DIR) / f"{service_id}-master-fifo"
#    write_master_fifo(fifo_file, command)


# @app.command(rich_help_panel="Control", short_help="Show logs of device")
# def logs(ctx: typer.Context, entity: str = typer.Argument("device")):
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    status = get_service_status(f"{entity}-emperor", conf)

#    log_file = Path(conf.LOG_DIR) / f"{entity}.log"
#    if log_file.exists() and log_file.is_file():
#        console.pager(
#            log_file.read_text(),
#            status_bar_format=f"{log_file.resolve()} (status: {status})"
#        )


# @app.command(rich_help_panel="Control", short_help="Show status of device (running or stopped)")
# def status(ctx: typer.Context):
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    status = get_service_status(f"device", conf)
#    if status == "running":
#        log_func = console.success
#    else:
#        log_func = console.error
#    log_func(f"Device is [b]{status}[/b]")


@app.command(rich_help_panel="Control", short_help="Attach to the PikeSquares Server")
@run_async
async def attach(
    ctx: typer.Context,
):
    """Attach to PikeSquares Server"""
    context = ctx.ensure_object(dict)
    pc = await services.aget(context, ProcessCompose)
    logger.info(pc)
    await pc.attach()


@app.command(rich_help_panel="Control", short_help="Launch a preconfigured app")
@run_async
async def launch(
    ctx: typer.Context,
):
    """Launch a preconfigured app or managed, self-hosted service"""

    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")

    conf = await services.aget(context, AppConfig)
    uow = await services.aget(context, UnitOfWork)
    plugin_manager = await services.aget(context, pluggy.PluginManager)

    machine_id = ServiceBase.read_machine_id()
    device = uow.devices.get_by_machine_id(machine_id)
    if not device:
        console.error(f"cli launch: unable to locate device by machine id {machine_id}")
        raise typer.Exit(code=0) from None

    # try:
    #    vassal_stats = next(filter(lambda v: v.id.split(".ini")[0], device_stats.vassals))
    #    print(vassal_stats)
    # except StopIteration:
    #    project_zmq_monitor = uow.zmq_monitors.get_by_project_id(project.id)
    #    vassals_home = project_zmq_monitor.uwsgi_zmq_address
    #    await project.up(device_zmq_monitor, vassals_home, tuntap_router)
    #
    #
    # launch_service_preconfigured: Literal["bugsink", "meshdb"]
    # launch_service_wsgi: Literal["python-wsgi-git"]
    launch_service = await prompt_for_launch_service(uow, custom_style)
    project = await prompt_for_project(launch_service, uow, plugin_manager, custom_style)
    if not project:
        console.error(f"cli launch: unable to select or provision project")
        raise typer.Exit(code=0) from None

    if not await project_up(project):
        console.error(f"Unable to launch project {project.name}")
        raise typer.Exit(code=0) from None

    http_routers = project.http_routers or []
    if not http_routers:
        console.error(f"Unable to locate an http router for project {project.name}")
        raise typer.Exit(code=0) from None

    if not await http_router_up(uow, http_routers[0]):
        console.error(f"Unable to launch http router for project {project.name}")
        raise typer.Exit(code=0) from None

    if launch_service in ["python-wsgi-git", "bugsink", "meshdb"]:
        # app_runtime_plugin_manager = await services.aget(context, AppRuntimePluginManager)
        # daemon_conf = conf.attached_daemon_plugins.get(launch_service)
        # if not daemon_conf:
        #    logger.error(f"unable to lookup attached daemon plugin {launch_service}")
        #    raise typer.Exit(1) from None

        # plugin_class = daemon_conf.get("class")
        # if not plugin_class:
        #    logger.error(f"unable to lookup {attached_daemon.name} class in config")

        # app_runtime_plugin_manager.register(PythonRuntimePlugin())
        # runtime_version = plugin_manager.hook.app_runtime_prompt_for_version()
        # console.info(f"selected Python {runtime_version}")
        runtime_version = "3.12"
        python_app_runtime = None
        wsgi_app = None
        try:
            python_app_runtime = await provision_python_app_runtime(runtime_version, uow, custom_style)
            python_app_codebase = await provision_app_codebase(
                launch_service,
                plugin_manager,
                AsyncPath(conf.pyapps_dir),
                AsyncPath(str(conf.UV_BIN)),
                uow,
                custom_style,
            )
            if not python_app_codebase:
                console.error(f"unable to provision the {launch_service} runtime.")
                raise typer.Exit(code=0) from None
        except Exception as exc:
            logger.exception(exc)
            console.error(f"unable to provision the {launch_service} runtime.")
            raise typer.Exit(code=0) from None

        with uow:
            try:
                wsgi_app = await provision_wsgi_app(
                    launch_service, AsyncPath(python_app_codebase.root_dir), uow, plugin_manager
                )
                if not wsgi_app:
                    console.error(f"unable to provision the {launch_service} app.")
                    raise typer.Exit(code=0) from None

                await wsgi_app_up(wsgi_app, uow, console)

            except Exception as exc:
                logger.exception(exc)
                uow.rollback()
                console.error(f"unable to provision the {launch_service} app.")
                raise typer.Exit(code=0) from None
            uow.commit()

    elif launch_service in ["postgres", "redis"]:
        attached_daemon_name = launch_service
        if not project:
            console.warning("no project selected. exiting")
            raise typer.Exit()

        # attached_daemons = uow.attached_daemons.list()
        # for daemon in attached_daemons:
        #    logger.info(daemon)
        # attached_daemon_choices = [d.service_id for d in attached_daemons]
        # create_data_dir  = True
        # if attached_daemon_name == "postgres":
        #    create_data_dir = False
        #
        # daemon_conf = conf.attached_daemon_plugins.get(launch_service)
        # if not daemon_conf:
        #    logger.error(f"unable to lookup attached daemon plugin {launch_service}")
        #    raise typer.Exit(1) from None
        attached_daemon = None
        try:
            attached_daemon = await provision_attached_daemon(
                attached_daemon_name,
                project,
                uow,
                plugin_manager,
            )
            if attached_daemon:
                attached_daemon_device = uow.tuntap_devices.get_by_linked_service_id(attached_daemon.service_id)

                await attached_daemon_up(
                    attached_daemon,
                    uow,
                    plugin_manager,
                )
                if 0:
                    if attached_daemon.ping("/usr/local/bin/redis-cli", attached_daemon_device.ip):
                        console.success(
                            f":heavy_check_mark:     Launching attached daemon [{attached_daemon_name}]. Done!"
                        )
                    else:
                        console.error(f"{attached_daemon_name} ping failed.")
        except Exception as exc:
            logger.exception(exc)
            uow.rollback()
            console.error(f"unable to provision the {launch_service} app.")
            raise typer.Exit(code=0) from None

        uow.commit()


@app.command(rich_help_panel="Control", short_help="Info on the PikeSquares Server")
@run_async
async def info(
    ctx: typer.Context,
):
    """Info on the PikeSquares Server"""
    context = ctx.ensure_object(dict)
    process_compose = await services.aget(context, ProcessCompose)
    processes = [
        ("device", "device manager"),
        ("caddy", "reverse proxy"),
        ("dnsmasq", "dns server"),
        # ("api", "PikeSquares API"),
    ]
    for process in processes:
        try:
            stats = await process_compose.ping_api(process[0])
            logger.debug(f"{process[0]} {stats=}")

            if stats.status == "Running":
                console.success(f":heavy_check_mark:     {process[1]} [process-compose] is running.")
            elif stats.status == "Completed":
                console.warning(f":heavy_exclamation_mark:     {process[1]} [process-compose] is not running.")
        except PCAPIUnavailableError:
            console.warning(":heavy_exclamation_mark:     Process Compose is not running.")
            break

    for svc in services.get_pings(context):
        logger.debug(f"pinging {svc.name=}")
        # pikesquares.domain.process_compose.DNSMASQProcess
        svc_name = svc.name.split(".")[-1]
        try:
            await svc.aping()
            # console.success(f":heavy_check_mark:     {svc_name} \[svcs] is running")
        except ServiceUnavailableError:
            console.warning(f":heavy_exclamation_mark:     {svc_name} is not running.")


@app.command(rich_help_panel="Control", short_help="tail the service log")
def tail_service_log(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """ """

    obj = ctx.ensure_object(dict)
    obj["cli-style"] = console.custom_style_dope

    # device = services.get(obj, Device)
    # show_config_start_marker = ";uWSGI instance configuration\n"
    # show_config_end_marker = ";end of configuration\n"

    # latest_running_config, latest_startup_log = device.startup_log(
    #     show_config_start_marker, show_config_end_marker
    # )
    # for line in latest_running_config:
    #     console.info(line)

    # for line in latest_startup_log:
    #     console.info(line)
