import os
from typing import Optional

import typer
from tinydb import TinyDB, where

from pikesquares import (
    HandlerFactory, 
    get_service_status,
)
from .console import console
from ..conf import ClientConfig


app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")

try:
    import sentry_sdk
except ImportError:
    pass
else:
    sentry_sdk.init(
        dsn="https://bbacdfaf17304b809e02b7ab39a64226@sentry.mirimus.com/17",
        traces_sample_rate=1.0
    )


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config: Optional[str] = typer.Option("", help="Path to configuration file."),
    verbose: Optional[bool] = typer.Option(False, help="Enable verbose mode."),
    version: Optional[bool] = typer.Option(False, help="Show version and exit."),
):
    """
    Welcome to Pike Squares
    """

    if version:
        from importlib import metadata
        console.info(metadata.version("pikesquares"))
        return

    assert os.environ.get("VIRTUAL_ENV"), "VIRTUAL_ENV not set"

    print(config)
    client_config = ClientConfig(_env_file=config or None)
    print(client_config)

    obj = ctx.ensure_object(dict)
    obj["verbose"] = verbose
    obj["client_config"] = client_config

    def get_project_db(project_name):
        device_db = obj['device']
        projects = device_db.search(
            (where('name') == project_name) &
            (where('type') == "Project")
        )
        if not projects:
            return
        project = projects[0]
        config_path = project.get('path')
        return TinyDB(f"{config_path}/{project_name}.vconf-project")

    def get_projects_db():
        device_db = obj['device']
        yield from device_db.search(
            (where('type') == "Project")
        )

    if 'device' not in obj:
        obj['device'] = TinyDB(f"{client_config.CONFIG_DIR}/device.json")

    if 'project' not in obj:
        obj['project'] = get_project_db
    
    if 'projects' not in obj:
        obj['projects'] = get_projects_db


@app.command(rich_help_panel="Control", short_help="Run device (if stopped)")
def up(
    ctx: typer.Context, 
    foreground: Optional[bool] = typer.Option(False, help="Run in foreground.")
):
    """ Start all services """

    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")
    client_config.DAEMONIZE = not foreground

    # What should user see if device is already started?
    status = get_service_status(f"device", client_config)
    if status == "running":
        console.info("Your device is already running")
        return

    device = HandlerFactory.make_handler("Device")(
        service_id="device", 
        client_config=client_config,
    )
    device.prepare_service_config()
    device.start()


@app.command(rich_help_panel="Control", short_help="Show logs of device")
def logs(ctx: typer.Context, entity: str = typer.Argument("device")):
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")

    status = get_service_status(f"{entity}-emperor", client_config)

    log_file = Path(client_config.LOG_DIR) / f"{entity}.log"
    if log_file.exists() and log_file.is_file():
        console.pager(
            log_file.read_text(),
            status_bar_format=f"{log_file.resolve()} (status: {status})"
        )


@app.command(rich_help_panel="Control", short_help="Show status of device (running or stopped)")
def status(ctx: typer.Context):
    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")
    
    status = get_service_status(f"device", client_config)
    if status == "running":
        log_func = console.success
    else:
        log_func = console.error
    log_func(f"Device is [b]{status}[/b]")


from .commands.projects import *
from .commands.apps import *


if __name__ == "__main__":
    app()
