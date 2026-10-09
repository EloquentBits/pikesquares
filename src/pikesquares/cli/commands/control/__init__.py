import os
import time
from pathlib import Path

import pluggy
import questionary
import structlog
import tenacity
import typer
from plumbum import FG, ProcessExecutionError
from plumbum import local as pl_local

from pikesquares import services
from pikesquares.cli.console import console
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
def up(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """Launch PikeSquares Server"""

    logger.info("running - pikesquares up")

    context = ctx.ensure_object(dict)

    conf = services.get(context, AppConfig)
    if not context["run_foreground"]:
        process_compose = services.get(context, ProcessCompose)

        # if conf and not conf.pyapps_dir.exists():
        #    logger.error(f"python apps directory @ {conf.pyapps_dir} is not available")
        #    raise typer.Exit(code=1) from None

        # if conf and not conf.attached_daemons_dir.exists():
        #    logger.error(f"attached daemons directory @ {conf.attached_daemons_dir} is not avai#lable")
        #    raise typer.Exit(code=1) from None

        try:
            _ = process_compose.ping_api("device")
            logger.info("process-compose is already running. not bringing it up now.")
        except PCAPIUnavailableError:
            logger.info("bringing up process-compose")
            up_result = process_compose.up()
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
                    process_stats = process_compose.ping_api(name)
                    if process_stats.is_running and process_stats.status == "Running":
                        console.success(f":heavy_check_mark:     {process.description}... Launched!")
                    else:
                        console.warning(f":heavy_exclamation_mark:     {process.description} unable to launch.")
                except PCAPIUnavailableError:
                    time.sleep(1)
                    continue
        except (StopIteration, IndexError):
            pass
    else:
        uow = services.get(context, UnitOfWork)
        machine_id = ServiceBase.read_machine_id()
        logger.info(f"{machine_id=}")
        device = uow.devices.get_by_machine_id(machine_id)
        if not device:
            console.error(f"cli up: unable to locate device by machine id {machine_id}")
            raise typer.Exit(code=0) from None

        cmd_env = {}
        # build the machine_id predicate with char() so the query contains no
        # single quotes (keeps it trivially embeddable in a shell-quoted command)
        machine_id_chars = ",".join(str(b) for b in machine_id.encode())
        sql = (
            "SELECT option_key,option_value FROM uwsgi_options "
            f"WHERE machine_id=char({machine_id_chars}) "
            "ORDER BY sort_order_index"
        )
        logger.info(sql)

        if cmd_env:
            pl_local.env.update(cmd_env)
            logger.debug(f"{cmd_env=}")

        # with pl_local.as_user(run_as_user):
        # uv = pl_local[str(conf.UV_BIN)]
        uwsgi_bin = pl_local[str(conf.data_dir / "bin/uwsgi")]
        uwsgi_bin_cmd = uwsgi_bin[
            "--show-config", "--plugin", str(conf.sqlite_plugin), "--sqlite", ":".join([str(conf.db_path), sql])
        ]

        # cwd = pl_local.path(str(conf.data_dir))
        console.info("Starting uWSGI Emperor")
        uwsgi_bin_cmd & FG()

        """
        try:
            result = uwsgi_bin.run_fg(
                cmd_args,
                cwd=str(cwd),
                **{"env": cmd_env}
            )
        except ProcessExecutionError as exc:
            for line in exc.stdout.split("\n"):
                print(line)

            if exc.stderr:
                logger.debug("start uWSGI Emperor -  errors:")
                for line in exc.stderr.split("\n"):
                    print(line)

            # if "#*** python plugin built and available in ./python_plugin.so ***" not in result.stdout:
            #    logger.error(f"unable to build the uWSIG python plugin for Python {py_version}")
            #    raise typer.Exit()

            return typer.Exit(code=1)
        """

        """
        projects = device.projects
        for project in projects:
            try:
                if project_up(project) or not project.read_stats():
                    console.success(f":heavy_check_mark:     Launched project [{project.name}]. Done!")
                    # process_compose.add_tail_log_process(project.name, project.log_file)
            except tenacity.RetryError:
                console.warning(f"Project {project.name} has not launched. Giving up.")
                continue
            except Exception as exc:
                logger.exception(exc)
                console.warning(f"Project {project.name} has not launched. Giving up.")
                continue

            project_http_routers = project.http_routers
            for http_router in project_http_routers:
                http_router_up_result = http_router_up(uow, http_router)
                if http_router_up_result:
                    console.success(":heavy_check_mark:     Launching http router.. Done!")
                    console.success(":heavy_check_mark:     Launching http router subscription server.. Done!")
                    # process_compose.add_tail_log_process(http_router.service_id, http_router.log_file)
        """

    console.success()
    console.success("PikeSquares API is available at: http://127.0.0.1:9000")
    console.success()
    console.success("Next steps: cd to your project directory and run `pikesquares init`")
    console.success()
    console.success("🚀 PikeSquares Server is up and running. 🚀")


@app.command(rich_help_panel="Control", short_help="Stop the PikeSquares Server (if running)")
def down(
    ctx: typer.Context,
):
    """Stop the PikeSquares Server"""

    context = ctx.ensure_object(dict)
    pc = services.get(context, ProcessCompose)
    try:
        retcode, stdout, stderr = pc.down()
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
def attach(
    ctx: typer.Context,
):
    """Attach to PikeSquares Server"""
    context = ctx.ensure_object(dict)
    pc = services.get(context, ProcessCompose)
    logger.info(pc)
    pc.attach()


@app.command(rich_help_panel="Control", short_help="Launch a preconfigured app")
def launch(
    ctx: typer.Context,
):
    """Launch a preconfigured app or managed, self-hosted service"""

    context = ctx.ensure_object(dict)
    custom_style = context.get("cli-style")

    conf = services.get(context, AppConfig)
    uow = services.get(context, UnitOfWork)
    plugin_manager = services.get(context, pluggy.PluginManager)

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
    #    project.up(device_zmq_monitor, vassals_home, tuntap_router)
    #
    #
    # launch_service_preconfigured: Literal["bugsink", "meshdb"]
    # launch_service_wsgi: Literal["python-wsgi-git"]
    launch_service = prompt_for_launch_service(uow, custom_style)
    project = prompt_for_project(launch_service, uow, plugin_manager, custom_style)
    if not project:
        console.error(f"cli launch: unable to select or provision project")
        raise typer.Exit(code=0) from None

    if not project_up(project):
        console.error(f"Unable to launch project {project.name}")
        raise typer.Exit(code=0) from None

    http_routers = project.http_routers or []
    if not http_routers:
        console.error(f"Unable to locate an http router for project {project.name}")
        raise typer.Exit(code=0) from None

    if not http_router_up(uow, http_routers[0]):
        console.error(f"Unable to launch http router for project {project.name}")
        raise typer.Exit(code=0) from None

    if launch_service in ["python-wsgi-git", "bugsink", "meshdb"]:
        # app_runtime_plugin_manager = services.get(context, AppRuntimePluginManager)
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
            python_app_runtime = provision_python_app_runtime(runtime_version, uow, custom_style)
            python_app_codebase = provision_app_codebase(
                launch_service,
                plugin_manager,
                Path(conf.pyapps_dir),
                Path(str(conf.UV_BIN)),
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

        try:
            wsgi_app = provision_wsgi_app(launch_service, Path(python_app_codebase.root_dir), uow, plugin_manager)
            if not wsgi_app:
                console.error(f"unable to provision the {launch_service} app.")
                raise typer.Exit(code=0) from None

            wsgi_app_up(wsgi_app, uow, console)

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
            attached_daemon = provision_attached_daemon(
                attached_daemon_name,
                project,
                uow,
                plugin_manager,
            )
            if attached_daemon:
                attached_daemon_device = uow.tuntap_devices.get_by_linked_service_id(attached_daemon.service_id)

                attached_daemon_up(
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
def info(
    ctx: typer.Context,
):
    """Info on the PikeSquares Server"""
    context = ctx.ensure_object(dict)
    process_compose = services.get(context, ProcessCompose)
    processes = [
        ("device", "device manager"),
        ("caddy", "reverse proxy"),
        ("dnsmasq", "dns server"),
        # ("api", "PikeSquares API"),
    ]
    for process in processes:
        try:
            stats = process_compose.ping_api(process[0])
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
            svc.ping()
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
