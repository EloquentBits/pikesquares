import sys
import shutil
import os
from typing import Optional

import typer
from typing_extensions import Annotated
from tinydb import TinyDB, Query

from .. import (
    load_client_conf,
    write_master_fifo,
    get_service_status, 
)
from ..services.device import (
    device_up, 
)
from .console import console
from .pki import (
        ensure_pki,
        ensure_build_ca,
        ensure_csr,
        ensure_sign_req,
)

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
    #pex_python = os.environ.get("PEX_PYTHON_PATH")
    #console.info(f"{pex_python=}")

    conf = load_client_conf()
    if not conf:
        console.warning("unable to load client config. exiting.")
        typer.Exit()
    #console.info(conf.model_dump())

    if all([
        ensure_pki(conf),
        ensure_build_ca(conf),
        ensure_csr(conf),
        ensure_sign_req(conf),]):
           console.success(f"Wildcard certificate created.")

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

    if get_service_status(Path(conf.RUN_DIR) / "device-stats.sock") == "running":
        console.info("Looks like a PikeSquares Server is already running")
        if questionary.confirm("Stop the running PikeSquares Server?").ask():
            write_master_fifo(str(Path(conf.RUN_DIR) / "device-master-fifo"), "q")
            console.success(f"PikeSquares Server has been shut down.")
        else:
            raise typer.Exit()

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
        write_master_fifo(str(Path(conf.RUN_DIR) / "device-master-fifo"), "q")
        console.success(f"PikeSquares Server has been shut down.")
        

@app.command(rich_help_panel="Control", short_help="Write to master fifo")
def write_to_master_fifo(
    ctx: typer.Context, 
    service_id: Annotated[str, typer.Option("--service-id", "-s", help="Service ID to send the command to")],
    command: Annotated[str, typer.Option("--command", "-c", help="Command to send master fifo.")],
):
    obj = ctx.ensure_object(dict)
    conf = obj.get("conf")

    service_id = service_id or "device"
    fifo_file = Path(conf.RUN_DIR) / f"{service_id}-master-fifo"
    write_master_fifo(fifo_file, command)


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
