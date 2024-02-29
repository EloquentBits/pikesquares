import sys
import os
from typing import Optional

import typer
from tinydb import TinyDB, Query

#from .. import (
#    get_service_status, 
#)
from ..services.device import device_up
#from ..services.project import project_up,

from .console import console
from .pki import (
        ensure_pki,
        ensure_build_ca,
        ensure_csr,
        ensure_sign_req,
)
from ..conf import ClientConfig

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verbose: Optional[bool] = typer.Option(False, help="Enable verbose mode."),
    version: Optional[bool] = typer.Option(False, help="Show version and exit."),
):
    """
    Welcome to Pike Squares
    """
    #for key, value in os.environ.items():
    #    print(f'{key}: {value}')
    if version:
        from importlib import metadata
        try:
            console.info(metadata.version("pikesquares"))
        except ModuleNotFoundError:
            console.info("unable to import pikesquares module.")
        return

    #os.environ.get('PIKESQUARES_SCIE_BINDINGS')
    data_dir = Path(os.environ.get("PIKESQUARES_DATA_DIR", ""))
    conf_mapping = {}
    with TinyDB(data_dir / "device-db.json") as db:
        conf_db = db.table('configs')
        try:
            conf_mapping = conf_db.search(Query().version == os.environ.get("PIKESQUARES_VERSION"))[0]
        except IndexError:
            print(f"unable to load conf from {str(data_dir)}/device-db.json")
            return

    conf = ClientConfig(**conf_mapping)
    console.info(conf.model_dump())

    if all([
        ensure_pki(conf),
        ensure_build_ca(conf),
        ensure_csr(conf),
        ensure_sign_req(conf),]):
           console.info(f"Wildcard certificate created.")

    #for k, v in conf.model_dump().items():
    #    if k.endswith("_DIR"):
    #        Path(v).mkdir(mode=0o777, parents=True, exist_ok=True)

    obj = ctx.ensure_object(dict)
    obj["verbose"] = verbose
    obj["conf"] = conf

    #console.warning("....exiting....")
    #sys.exit()


@app.command(rich_help_panel="Control", short_help="Run device (if stopped)")
def up(
    ctx: typer.Context, 
    foreground: Optional[bool] = typer.Option(
        True, 
        help="Run in foreground."
    )
):
    """ Start all services """

    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")
    conf.DAEMONIZE = not foreground

    # What should user see if device is already started?
    #status = get_service_status(f"device", conf)
    #if status == "running":
    #    console.info("Your device is already running")
    #    return

    device_up(conf)

    #for project_doc in db.table('projects'):
    #    project_up(conf, project_doc.service_id)


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

from .commands.routers import *
from .commands.projects import *
from .commands.apps import *


if __name__ == "__main__":
    app()
