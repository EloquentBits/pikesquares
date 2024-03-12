import sys
import shutil
import os
from typing import Optional

import typer
from typing_extensions import Annotated
from tinydb import TinyDB, Query

#from .. import (
#    get_service_status, 
#)
from ..services.device import (
    device_up, 
    device_write_fifo,
)
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
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose mode.")] = False,
    version: Annotated[bool, typer.Option("--version", "-V", help="Show version and exit.")] = False,
    cli_style: Annotated[str, typer.Option("--cli-style", "-c", help="Custom CLI Style")] = "dope",
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
        raise typer.Exit()

    #print(f"{os.environ.get('PIKESQUARES_SCIE_BINDINGS')=}")
    #print(f"{os.environ.get('VIRTUAL_ENV')=}")

    data_dir = Path(os.environ.get("PIKESQUARES_DATA_DIR", ""))

    #pex_python = os.environ.get("PEX_PYTHON_PATH")
    #console.info(f"{pex_python=}")

    if not (Path(data_dir) / "device-db.json").exists():
        console.warning(f"conf db does not exist @ {data_dir}/device-db.json")
        sys.exit()

    conf_mapping = {}
    pikesquares_version = os.environ.get("PIKESQUARES_VERSION")
    with TinyDB(data_dir / "device-db.json") as db:
        try:
            conf_mapping = db.table('configs').\
                search(Query().version == pikesquares_version)[0]
        except IndexError:
            console.warning(f"unable to load v{pikesquares_version} conf from {str(data_dir)}/device-db.json")
            raise typer.Exit()

    conf = ClientConfig(**conf_mapping)
    #console.info(conf.model_dump())

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
    obj["cli-style"] = getattr(
        console, 
        f"custom_style_{cli_style}", 
        getattr(console, f"custom_style_{conf.CLI_STYLE}"),
    )
            
    #console.warning("....exiting....")
    #sys.exit()

@app.command(rich_help_panel="Control", short_help="Run device (if stopped)")
def up(
    ctx: typer.Context, 
    foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """ Launch PikeSquares Server """

    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")
    conf.DAEMONIZE = not foreground

    # What should user see if device is already started?
    #status = get_service_status(f"device", conf)
    #if status == "running":
    #    console.info("Your device is already running")
    #    return

    device_up(conf, console)

    #for project_doc in db.table('projects'):
    #    project_up(conf, project_doc.service_id)


@app.command(rich_help_panel="Control", short_help="Reset device")
def reset(
    ctx: typer.Context, 
    shutdown: Optional[str] = typer.Option("", "--shutdown", help="Shutdown PikeSquares server after reset."),
):
    """ Reset PikeSquares Installation """

    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    if not questionary.confirm("Reset PikeSquares Installation?").ask():
        raise typer.Exit()

    if questionary.confirm("Drop db tables?").ask():
        with TinyDB(Path(conf.DATA_DIR) / "device-db.json") as db:
            db.drop_table('projects')
            db.drop_table('routers')
            db.drop_table('apps')

    if questionary.confirm("Delete all configs").ask():
        for proj_config in (Path(conf.CONFIG_DIR) / "projects").glob("project_*.json"):
            for app_config in (Path(conf.CONFIG_DIR) / \
                    proj_config.stem / "apps").glob("*.json"):
                console.info(f"found loose app config. deleting {app_config.name}")
                app_log = Path(conf.LOG_DIR) / app_config.stem / ".log"
                app_log.unlink(missing_ok=True)
                app_config.unlink()

            console.info(f"found loose project config. deleting {proj_config.name}")
            proj_config.unlink()

        for router_config in (Path(conf.CONFIG_DIR) / "projects").glob("router_*.json"):
            console.info(f"found loose router config. deleting {router_config.name}")
            router_config.unlink()

    if shutdown or questionary.confirm("Shutdown PikeSquares Server").ask():
        device_write_fifo(conf, "q")
        console.info(f"PikeSquares Server has been shut down.")
        

@app.command(rich_help_panel="Control", short_help="Write to master fifo")
def write_master_fifo(
    ctx: typer.Context, 
    service_id: Annotated[str, typer.Option("--service-id", "-s", help="Service ID to send the command to")],
    command: Annotated[str, typer.Option("--command", "-c", help="Command to send master fifo.")],
):
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    service_id = service_id or "device"
    fifo_file = Path(conf.RUN_DIR) / f"{service_id}-master-fifo"

    with open(fifo_file, "w") as master_fifo:
       master_fifo.write(command)
       console.log(f"sent command [{command}] to {service_id} master fifo")

    #device_write_fifo(conf, command, console)

    """
    ‘0’ to ‘9’ - set the fifo slot (see below)
    ‘+’ - increase the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
    ‘-’ - decrease the number of workers when in cheaper mode (add --cheaper-algo manual for full control)
    ‘B’ - ask Emperor for reinforcement (broodlord mode, requires uWSGI >= 2.0.7)
    ‘C’ - set cheap mode
    ‘c’ - trigger chain reload
    ‘E’ - trigger an Emperor rescan
    ‘f’ - re-fork the master (dangerous, but very powerful)
    ‘l’ - reopen log file (need –log-master and –logto/–logto2)
    ‘L’ - trigger log rotation (need –log-master and –logto/–logto2)
    ‘p’ - pause/resume the instance
    ‘P’ - update pidfiles (can be useful after master re-fork)
    ‘Q’ - brutally shutdown the instance
    ‘q’ - gracefully shutdown the instance
    ‘R’ - send brutal reload
    ‘r’ - send graceful reload
    ‘S’ - block/unblock subscriptions
    ‘s’ - print stats in the logs
    ‘W’ - brutally reload workers
    ‘w’ - gracefully reload workers
    """


@app.command(rich_help_panel="Control", short_help="Nuke installation")
def uninstall(
    ctx: typer.Context, 
    dry_run: Optional[bool] = typer.Option(
        False, 
        help="Uninstall dry run"
    )
):
    """ Delete the entire PikeSquares installation """

    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    for user_dir in [
            conf.DATA_DIR, 
            conf.CONFIG_DIR, 
            conf.RUN_DIR, 
            conf.LOG_DIR,
            conf.PLUGINS_DIR,
            conf.PKI_DIR]:
        if not dry_run:
            try:
                shutil.rmtree(user_dir)
            except FileNotFoundError:
                pass
        console.info(f"removing {user_dir}")
    console.info("PikeSquares has been uninstalled.")


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
