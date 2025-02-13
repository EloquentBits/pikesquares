from typing import Optional, Annotated

import typer
import questionary
import structlog

from pikesquares.cli.console import console
from pikesquares import services
from pikesquares.services.base import StatsReadError
from pikesquares.services.device import Device

logger = structlog.get_logger()

app = typer.Typer()


@app.command(short_help="Launch the PikeSquares Server (if stopped)")
@app.command()
def up(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """Launch PikeSquares Server"""
    context = ctx.ensure_object(dict)
    # client_conf = services.get(context, conf.ClientConfig)
    device = services.get(context, Device)
    if device.get_service_status() == "running":
        console.info("Looks like a PikeSquares Server is already running")
        if questionary.confirm("Stop the running PikeSquares Server and launch a new instance?").ask():
            device.stop()
            console.success("PikeSquares Server has been shut down.")
        else:
            raise typer.Exit()
    device.up()


@app.command(rich_help_panel="Control", short_help="Stop the PikeSquares Server (if running)")
def down(
    ctx: typer.Context,
    noinput: Annotated[bool, typer.Option(help="Do not prompt.")] = False
):
    """Stop the PikeSquares Server"""

    obj = ctx.ensure_object(dict)
    obj["cli-style"] = console.custom_style_dope

    svc_device = services.get(obj, Device)
    if svc_device.get_service_status() == "running":
        if noinput:
            svc_device.stop()
        elif questionary.confirm("Stop the running PikeSquares Server?").ask():
            svc_device.stop()
            console.success("PikeSquares Server has been shut down.")
        else:
            raise typer.Exit()


#@app.command(rich_help_panel="Control", short_help="Reset device")
def reset(
    ctx: typer.Context, 
    shutdown: Optional[str] = typer.Option("", "--shutdown", help="Shutdown PikeSquares server after reset."),
):
    """ Reset PikeSquares Installation """

    context = ctx.ensure_object(dict)
    svc_device = services.get(context, Device)

    if not questionary.confirm("Reset PikeSquares Installation?").ask():
        raise typer.Exit()

    if questionary.confirm("Drop db tables?").ask():
        svc_device.drop_db_tables()

    if questionary.confirm("Delete all configs").ask():
        svc_device.delete_configs()

    if shutdown or questionary.confirm("Shutdown PikeSquares Server").ask():
        svc_device.write_master_fifo("q")
        console.success("PikeSquares Server has been shut down.")


#@app.command(rich_help_panel="Control", short_help="Nuke installation")
def uninstall(
    ctx: typer.Context,
    dry_run: Optional[bool] = typer.Option(
        False,
        help="Uninstall dry run"
    )
):
    """ Delete the entire PikeSquares installation """

    context = ctx.ensure_object(dict)
    svc_device = services.get(context, Device)

    svc_device.uninstall(dry_run=dry_run)
    console.info("PikeSquares has been uninstalled.")


@app.command(short_help="Show PikeSquares Server Stats)")
@app.command()
def info(
    ctx: typer.Context,
    # foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """Show PikeSquares Server Stats"""

    context = ctx.ensure_object(dict)
    # client_conf = services.get(context, conf.ClientConfig)
    device = services.get(context, Device)
    try:
        device_stats = device.stats()
    except StatsReadError:
        console.warning(f"""Device stats @ {device.stats_address} are unavailable.\nIs the PikeSquares Server running?""")
        raise typer.Exit() from None

    logger.info(device_stats)

    #vassals = stats_js.get("vassals", [])
    #console.info(f"{len(vassals)} vassals running")
    #for vs in vassals:
    #    vassal_id = vs.get("id")
    #    loyal = vs.get("loyal")
    #    ready = vs.get("ready")
    #    accepting = vs.get("accepting")
    #    console.info(f"{vassal_id=} {loyal=} {ready=} {accepting=}")

#@app.command(rich_help_panel="Control", short_help="Write to master fifo")
#def write_to_master_fifo(
#    ctx: typer.Context, 
#    service_id: Annotated[str, typer.Option("--service-id", "-s", help="Service ID to send the command to")],
#    command: Annotated[str, typer.Option("--command", "-c", help="Command to send master fifo.")],
#):
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    service_id = service_id or "device"
#    fifo_file = Path(conf.RUN_DIR) / f"{service_id}-master-fifo"
#    write_master_fifo(fifo_file, command)


#@app.command(rich_help_panel="Control", short_help="Show logs of device")
#def logs(ctx: typer.Context, entity: str = typer.Argument("device")):
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")

#    status = get_service_status(f"{entity}-emperor", conf)

#    log_file = Path(conf.LOG_DIR) / f"{entity}.log"
#    if log_file.exists() and log_file.is_file():
#        console.pager(
#            log_file.read_text(),
#            status_bar_format=f"{log_file.resolve()} (status: {status})"
#        )


#@app.command(rich_help_panel="Control", short_help="Show status of device (running or stopped)")
#def status(ctx: typer.Context):
#    obj = ctx.ensure_object(dict)
#    conf = obj.get("conf")
    
#    status = get_service_status(f"device", conf)
#    if status == "running":
#        log_func = console.success
#    else:
#        log_func = console.error
#    log_func(f"Device is [b]{status}[/b]")

