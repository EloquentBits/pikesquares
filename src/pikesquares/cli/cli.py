import os
from typing import Optional
from pathlib import Path

import typer
#from typing_extensions import Annotated
import questionary
from tinydb import TinyDB, Query

from pikesquares.services import HandlerFactory, Device

from ..conf import ClientConfig
from ..services import (
    init_context,
    register_factory,
    get as svcs_get,
)
from ..services.device import *
from ..services.project import *
from ..services.router import *
from ..services.app import *

from .console import console
from pikesquares import __app_name__, __version__

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")


@app.command(rich_help_panel="Control", short_help="Reset device")
def reset(
    ctx: typer.Context, 
    shutdown: Optional[str] = typer.Option("", "--shutdown", help="Shutdown PikeSquares server after reset."),
):
    """ Reset PikeSquares Installation """

    #obj = ctx.ensure_object(dict)

    device_handler = HandlerFactory.make_handler("Device")(
        Device(service_id="device")
    )
    if not questionary.confirm("Reset PikeSquares Installation?").ask():
        raise typer.Exit()

    if all([
        device_handler.svc_model.get_service_status() == "running",
        shutdown or questionary.confirm("Shutdown PikeSquares Server").ask()
        ]):
        device_handler.stop()
        console.success(f"PikeSquares Server has been shut down.")

    if questionary.confirm("Drop db tables?").ask():
        device_handler.drop_db_tables()

    if questionary.confirm("Delete all configs and logs?").ask():
        device_handler.delete_configs()


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

@app.command(
        rich_help_panel="Control", short_help="Launch the PikeSquares Server (if stopped)"
)
def up(
    ctx: typer.Context, 
    #foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """ Launch PikeSquares Server """

    obj = ctx.ensure_object(dict)

    print(f"up: {obj=}")

    db = svcs_get(obj, TinyDB)
    #container = svcs.Container(registry)
    #db = container.get(TinyDB)
    if db.tables():
        print("reading tables....")
        for t in db.tables():
            print(t)
    else:
        print(f"unable to read db: {db}")

    conf = svcs_get(obj, ClientConfig)

    print(conf)

    #device_handler = obj["device-handler"]
    device_handler = svcs_get(obj, DeviceService)
    if device_handler.svc_model.get_service_status() == "running":
        console.info("Looks like a PikeSquares Server is already running")
        if questionary.confirm("Stop the running PikeSquares Server and launch a new instance?").ask():
            device_handler.stop()
            console.success(f"PikeSquares Server has been shut down.")
        else:
            raise typer.Exit()
    device_handler.up()

@app.command(
        rich_help_panel="Control", short_help="Stop the PikeSquares Server (if running)"
)
def down(
    ctx: typer.Context, 
    #foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """ Stop the PikeSquares Server """

    obj = ctx.ensure_object(dict)
    obj["cli-style"] = console.custom_style_dope

    device_handler = HandlerFactory.make_handler("Device")(
        Device(service_id="device")
    )
    if device_handler.svc_model.get_service_status() == "running":
        if questionary.confirm("Stop the running PikeSquares Server?").ask():
            device_handler.stop()
            console.success(f"PikeSquares Server has been shut down.")
        else:
            raise typer.Exit()


@app.command(
        rich_help_panel="Control", short_help="tail the service log"
)
def tail_service_log(
    ctx: typer.Context, 
    #foreground: Annotated[bool, typer.Option(help="Run in foreground.")] = True
):
    """ """

    obj = ctx.ensure_object(dict)
    obj["cli-style"] = console.custom_style_dope

    device_handler = HandlerFactory.make_handler("Device")(
        Device(service_id="device")
    )
    show_config_start_marker = ';uWSGI instance configuration\n'
    show_config_end_marker = ';end of configuration\n'

    latest_running_config, latest_startup_log = \
            device_handler.svc_model.startup_log(
                    show_config_start_marker, show_config_end_marker)
    for line in latest_running_config:
        console.info(line)

    for line in latest_startup_log:
        console.info(line)


from ..services.device import *
from .commands import apps
from .commands import managed_services

app.add_typer(
        apps.app, 
        name="apps"
    )

app.add_typer(
        managed_services.app, 
        name="services"
    )

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
    )
) -> None:
    """
    Welcome to Pike Squares. Building blocks for your apps.
    """

    print(f"About to execute command: {ctx.invoked_subcommand}")

    obj = ctx.ensure_object(dict)
    obj = init_context(obj)

    data_dir = Path(os.environ.get("PIKESQUARES_DATA_DIR", 
                        "/home/pk/.local/share/pikesquares")
    )
    db_path = Path(data_dir) / "device-db.json"
    if not db_path.exists():
        raise Exception(f"conf db does not exist @ {db_path}")

    def tinydb_factory():
        with TinyDB(db_path) as db:
            yield db

    register_factory(obj, TinyDB, tinydb_factory)

    def conf_factory():
        conf_mapping = {}
        pikesquares_version = os.environ.get("PIKESQUARES_VERSION")
        db = svcs_get(obj, TinyDB)
        try:
            conf_mapping = db.table('configs').\
                search(Query().version == pikesquares_version)[0]
        except IndexError:
            raise Exception(
                f"unable to load v{pikesquares_version} conf from {str(db_path)}"
            )
        return ClientConfig(**conf_mapping)

    register_factory(obj, ClientConfig, conf_factory)

    def device_handler_factory():
        return HandlerFactory.make_handler("Device")(
                Device(
                    conf=svcs_get(obj, ClientConfig),
                    service_id="device",
                )
        )
    register_factory(obj, DeviceService, device_handler_factory)
    #obj["device-handler"] = device_handler
    obj["cli-style"] = console.custom_style_dope

    

    #for key, value in os.environ.items():
    #    if key.startswith(('PIKESQUARES', 'SCIE', 'PEX')):
    #        print(f'{key}: {value}')

    # PIKESQUARES_VERSION: 0.0.13.dev0
    # SCIE: /home/pk/dev/eqb/scie-pikesquares/dist/scie-pikesquares-linux-x86_64
    # SCIE_ARGV0: /home/pk/dev/eqb/scie-pikesquares/dist/scie-pikesquares-linux-x86_64
    # PIKESQUARES_BIN_NAME: scie-pikesquares
    # PIKESQUARES_DEBUG:
    # SCIE_PIKESQUARES_VERSION: 0.0.26
    # PIKESQUARES_BUILDROOT_OVERRIDE:
    # PIKESQUARES_SCIE_BINDINGS: /home/pk/.cache/nce/104e9a801b64d5745c20ec1181e26fd7afb0d0bdde7de368ff55ced1e0ea420a/bindings
    # PEX_PYTHON_PATH: /home/pk/.cache/nce/57a37b57f8243caa4cdac016176189573ad7620f0b6da5941c5e40660f9468ab/cpython-3.12.2+20240224-x86_64-unknown-linux-gnu-install_only.tar.gz/python/bin/python3.12
    # PEX_ROOT: /home/pk/.cache/nce/104e9a801b64d5745c20ec1181e26fd7afb0d0bdde7de368ff55ced1e0ea420a/bindings/pex_root
    # PIKESQUARES_DATA_DIR: /home/pk/.local/share/pikesquares
    # PIKESQUARES_EASY_RSA_DIR: /home/pk/.cache/nce/aaa48fadcbb77511b9c378554ef3eae09f8c7bc149d6f56ba209f1c9bab98c6e/easyrsa
    # _PIKESQUARES_SERVER_EXE:

    #print(f"{os.environ.get('PIKESQUARES_SCIE_BINDINGS')=}")
    #print(f"{os.environ.get('VIRTUAL_ENV')=}")
    #pex_python = os.environ.get("PEX_PYTHON_PATH")
    #console.info(f"{pex_python=}")

    #console.info(device_handler.svc_model.model_dump())

    #getattr(
    #    console, 
    #    f"custom_style_{cli_style}", 
    #    getattr(console, f"custom_style_{conf.CLI_STYLE}"),
    #)

    return

"""
@app.callback(invoke_without_command=True)
def main_bak(
    ctx: typer.Context,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose mode.")] = False,
    version: Annotated[bool, typer.Option("--version", "-V", help="Show version and exit.")] = False,
    #cli_style: Annotated[str, typer.Option("--cli-style", "-c", help="Custom CLI Style")] = "dope",
):            
"""

#from .commands.routers import *
#from .commands.projects import *

#ALIASES = ("applications", "app")
#HELP = f"""
#    Application commands.\n
#    Aliases: [i]{', '.join(ALIASES)}[/i]
#"""

#apps_cmd = typer.Typer(
#    no_args_is_help=True,
#    rich_markup_mode="rich",
#    name="apps",
#    help=HELP
#)
#for alias in ALIASES:
#    app.add_typer(
#        apps_cmd,
#        name=alias,
#        help=HELP,
#        hidden=True
#    )
