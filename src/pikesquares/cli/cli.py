import os
from typing import Optional
from pathlib import Path

import typer

# from typing_extensions import Annotated
import questionary
from tinydb import TinyDB, Query
#from circus import Arbiter, get_arbiter

from pikesquares import conf, DEFAULT_DATA_DIR
from pikesquares import services
from pikesquares.services.device import Device
from pikesquares.services import process_compose
# from ..services.project import *
# from ..services.router import *
# from ..services.app import *

from .console import console
from pikesquares import __app_name__, __version__

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(rich_help_panel="Control", short_help="Reset device")
def reset(
    ctx: typer.Context,
    shutdown: Optional[str] = typer.Option("", "--shutdown", help="Shutdown PikeSquares server after reset."),
):
    """Reset PikeSquares Installation"""

    context = ctx.ensure_object(dict)
    device = services.get(context, Device)

    if not questionary.confirm("Reset PikeSquares Installation?").ask():
        raise typer.Exit()

    if all(
        [
            device.get_service_status() == "running",
            shutdown or questionary.confirm("Shutdown PikeSquares Server").ask(),
        ]
    ):
        device.stop()
        console.success("PikeSquares Server has been shut down.")

    if questionary.confirm("Drop db tables?").ask():
        device.drop_db_tables()

    if questionary.confirm("Delete all configs and logs?").ask():
        device.delete_configs()


@app.command(rich_help_panel="Control", short_help="Nuke installation")
def uninstall(ctx: typer.Context, dry_run: Optional[bool] = typer.Option(False, help="Uninstall dry run")):
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


@app.command(
        rich_help_panel="Control",
        short_help="Attach to the PikeSquares Server")
def attach(
    ctx: typer.Context,
):
    """Attach to PikeSquares Server"""

    context = ctx.ensure_object(dict)
    pc = services.get(context, process_compose.ProcessCompose)
    pc.attach()


@app.command(
        rich_help_panel="Control",
        short_help="Launch the PikeSquares Server (if stopped)")
def up(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """Launch PikeSquares Server"""

    # context = ctx.ensure_object(dict)
    # client_conf = services.get(context, conf.ClientConfig)
    # nothing to do here
    pass



@app.command(rich_help_panel="Control", short_help="Stop the PikeSquares Server (if running)")
def down(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """Stop the PikeSquares Server"""
    # obj = ctx.ensure_object(dict)
    # nothing to do here
    pass


@app.command(rich_help_panel="Control", short_help="tail the service log")
def tail_service_log(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """ """

    obj = ctx.ensure_object(dict)
    obj["cli-style"] = console.custom_style_dope

    device = services.get(obj, Device)
    show_config_start_marker = ";uWSGI instance configuration\n"
    show_config_end_marker = ";end of configuration\n"

    latest_running_config, latest_startup_log = device.startup_log(
        show_config_start_marker, show_config_end_marker
    )
    for line in latest_running_config:
        console.info(line)

    for line in latest_startup_log:
        console.info(line)


from .commands import devices
from .commands import apps
from .commands import managed_services

app.add_typer(apps.app, name="apps")
app.add_typer(devices.app, name="devices")
app.add_typer(managed_services.app, name="services")


def _version_callback(value: bool) -> None:
    if value:
        console.info(f"{__app_name__} v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show PikeSquares version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """
    Welcome to Pike Squares. Building blocks for your apps.
    """
    pikesquares_version = os.environ.get("PIKESQUARES_VERSION")

    for key, value in os.environ.items():
        if key.startswith(("PIKESQUARES", "SCIE", "PEX")):
            print(f"{key}: {value}")

    print(f"PikeSquares: v{pikesquares_version} About to execute command: {ctx.invoked_subcommand}")
    # context = services.init_context(ctx.ensure_object(dict))

    context = services.init_app(ctx.ensure_object(dict))

    data_dir = os.environ.get("PIKESQUARES_DATA_DIR")
    dbname = "device-db.json"
    if data_dir and Path(data_dir).exists():
        db_path = Path(data_dir) / dbname
    else:
        db_path = DEFAULT_DATA_DIR / dbname

    services.register_db(context, db_path)
    try:
        conf_mapping = services.get(context, TinyDB).\
                table("configs").\
                search(Query().version == pikesquares_version)[0]
    except IndexError:
        print(f"unable to load v{pikesquares_version} conf from {str(db_path)}")
        raise typer.Exit() from None

    services.register_app_conf(context, conf_mapping)
    client_conf = services.get(context, conf.ClientConfig)

    # console.debug(client_conf.model_dump())
    services.register_device(context, Device)

    pc_api_port = 9555
    process_compose.register_process_compose(context, client_conf, pc_api_port)
    pc = services.get(context, process_compose.ProcessCompose)

    for svc in services.get_pings(context):
        print(f"pinging {svc.name=}")
        try:
            svc.ping()
            print("process-compose is UP")
            if ctx.invoked_subcommand == "up":
                console.info("looks like PikeSquares Server is already running.")
                console.info("try `pikesquares attach` to see running processes.")
        except process_compose.ProcessComposeUnavailableException:
            print(f"process-compose is DOWN")
            # process-compose is not running
            # launch process-compose if
            pc.up()
            if ctx.invoked_subcommand == "up":
                raise typer.Exit() from None

    # def circus_arbiter_factory():
    #    watchers = []
    #    check_delay = 5
    #    endpoint = "tcp://127.0.0.1:5555"
    #    pubsub_endpoint = "tcp://127.0.0.1:5556"
    #    stats_endpoint = "tcp://127.0.0.1:5557"

    #    return Arbiter(
    #        watchers,
    #        endpoint=endpoint,
    #        pubsub_endpoint=pubsub_endpoint,
    #        stats_endpoint=stats_endpoint,
    #        check_delay = check_delay,
    #    )

    #services.register_factory(context, Arbiter, get_arbiter)

    # obj["device-handler"] = device_handler
    context["cli-style"] = console.custom_style_dope

    # console.info(device_handler.svc_model.model_dump())

    # getattr(
    #    console,
    #    f"custom_style_{cli_style}",
    #    getattr(console, f"custom_style_{conf.CLI_STYLE}"),
    # )


"""
@app.callback(invoke_without_command=True)
def main_bak(
    ctx: typer.Context,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose mode.")] = False,
    version: Annotated[bool, typer.Option("--version", "-V", help="Show version and exit.")] = False,
    #cli_style: Annotated[str, typer.Option("--cli-style", "-c", help="Custom CLI Style")] = "dope",
):            
"""

# from .commands.routers import *
# from .commands.projects import *

# ALIASES = ("applications", "app")
# HELP = f"""
#    Application commands.\n
#    Aliases: [i]{', '.join(ALIASES)}[/i]
# """

# apps_cmd = typer.Typer(
#    no_args_is_help=True,
#    rich_markup_mode="rich",
#    name="apps",
#    help=HELP
# )
# for alias in ALIASES:
#    app.add_typer(
#        apps_cmd,
#        name=alias,
#        help=HELP,
#        hidden=True
#    )
