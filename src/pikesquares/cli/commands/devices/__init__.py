from typing import Optional

import typer
from typing_extensions import Annotated

import questionary

from pikesquares.cli.console import console
from pikesquares.services import Device, HandlerFactory

#app = typer.Typer()

#@app.command(rich_help_panel="Control", short_help="Reset device")
def reset(
    ctx: typer.Context, 
    shutdown: Optional[str] = typer.Option("", "--shutdown", help="Shutdown PikeSquares server after reset."),
):
    """ Reset PikeSquares Installation """

    obj = ctx.ensure_object(dict)

    device_handler = HandlerFactory.make_handler("Device")(
        Device(service_id="device")
    )

    if not questionary.confirm("Reset PikeSquares Installation?").ask():
        raise typer.Exit()

    if questionary.confirm("Drop db tables?").ask():
        device_handler.drop_db_tables()

    if questionary.confirm("Delete all configs").ask():
        device_handler.delete_configs()

    if shutdown or questionary.confirm("Shutdown PikeSquares Server").ask():
        device_handler.write_master_fifo("q")
        console.success(f"PikeSquares Server has been shut down.")

#@app.command(rich_help_panel="Control", short_help="Nuke installation")
def uninstall(
    ctx: typer.Context, 
    dry_run: Optional[bool] = typer.Option(
        False, 
        help="Uninstall dry run"
    )
):
    """ Delete the entire PikeSquares installation """

    obj = ctx.ensure_object(dict)

    device_handler = HandlerFactory.make_handler("Device")(
        Device(service_id="device")
    )
    device_handler.uninstall(dry_run=dry_run)
    console.info("PikeSquares has been uninstalled.")

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

