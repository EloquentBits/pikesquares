import os
from typing import Optional

import typer
from tinydb import TinyDB

from .. import (
    get_service_status, 
    device_up,
    #project_up,
)
from .console import console
from ..conf import ClientConfig

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")

#try:
#    import sentry_sdk
#except ImportError:
#    pass
#else:
#    sentry_sdk.init(
#        dsn="https://bbacdfaf17304b809e02b7ab39a64226@sentry.mirimus.com/17",
#        traces_sample_rate=1.0
#    )


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config: Optional[str] = typer.Option(
        "/opt/pikesquares/pikesquares.conf", 
        help="Path to configuration file."
    ),
    verbose: Optional[bool] = typer.Option(False, help="Enable verbose mode."),
    version: Optional[bool] = typer.Option(False, help="Show version and exit."),
):
    """
    Welcome to Pike Squares
    """

    if version:
        from importlib import metadata
        try:
            console.info(metadata.version("pikesquares"))
        except ModuleNotFoundError:
            console.info("unable to import pikesquares module.")
        return

    venv_dir = os.environ.get("VIRTUAL_ENV")
    console.info(f"Using Python Virtual Environment @ {venv_dir}")

    assert os.environ.get("VIRTUAL_ENV"), "VIRTUAL_ENV not set"

    client_config = ClientConfig(_env_file=config or None)
    for k, v in client_config.model_dump().items():
        if k.endswith("_DIR"):
            Path(v).mkdir(mode=0o777, parents=True, exist_ok=True)

    obj = ctx.ensure_object(dict)
    obj["verbose"] = verbose
    obj["client_config"] = client_config
    obj['db'] = TinyDB(f"{Path(client_config.DATA_DIR) / 'device-db.json'}")

    """
    def get_project_db(project_uid):
        device_db = obj['device']
        projects = device_db.search(
            (where('cuid') == project_cuid) &
            (where('type') == "Project")
        )
        if not projects:
            return
        project = projects[0]
        config_path = project.get('path')
        return TinyDB(f"{config_path}/{project_uid}.json")

    def get_projects_db():
        device_db = obj['device']
        yield from device_db.search(
            (where('type') == "Project")
        )

    def get_router_db(router_id):
        device_db = obj['device']
        routers = device_db.search(
            (where('name') == router_id) &
            (where('type') == "Router")
        )
        if not routers:
            return
        router = routers[0]
        config_path = router.get('path')
        return TinyDB(f"{config_path}/{router_id}.json")

    def get_routers_db():
        device_db = obj['device']
        yield from device_db.search(
            (where('type') == "Router")
        )

    #if 'device' not in obj:
    #    obj['device'] = TinyDB(f"{client_config.DATA_DIR}/device-db.json")

    if 'project' not in obj:
        obj['project'] = get_project_db
    
    if 'projects' not in obj:
        obj['projects'] = get_projects_db

    if 'router' not in obj:
        obj['router'] = get_router_db
    
    if 'routers' not in obj:
        obj['routers'] = get_routers_db
    """

@app.command(rich_help_panel="Control", short_help="Run device (if stopped)")
def up(
    ctx: typer.Context, 
    foreground: Optional[bool] = typer.Option(
        True, 
        help="Run in foreground."
    )
):
    """ Start all services """


    venv_dir = os.environ.get("VIRTUAL_ENV")
    console.info(f"Using Python Virtual Environment @ {venv_dir}")
    print("UP UP UP")

    obj = ctx.ensure_object(dict)
    client_config = obj.get("client_config")
    client_config.DAEMONIZE = not foreground

    # What should user see if device is already started?
    status = get_service_status(f"device", client_config)
    if status == "running":
        console.info("Your device is already running")
        return

    device_up(client_config)

    #for project_doc in db.table('projects'):
    #    project_up(client_config, project_doc.service_id)

    """
    #routers = {p.get('name'): p.get('cuid') for p in obj['projects']()}
    routers = obj['routers']()
    #router_db = obj['router'](router_id)

    if routers:
        for router in routers:
            device = HandlerFactory.make_handler("Https-Router")(
                service_id=router_id, 
                client_config=client_config,
            )
            device.prepare_service_config()
            device.start()
    else:
        router_id = f"router_{cuid()}"
        device_db = obj['device']
        device_db.insert({
            'cuid': router_id,
            'type': "HttpsRouter",
            #'path': str(project_dir.resolve())
        })

        router = HandlerFactory.make_handler("Https-Router")(
            service_id=router_id, 
            client_config=client_config,
        )
        router.prepare_service_config()
        router.start()


    proj_db = obj['project'](project_name)

    project = HandlerFactory.make_handler("Project")(
        service_id=project_id,
        client_config=client_config,
    )
    proj_data = {
        "cuid": project_id,
        "name": project_name,
        "path": str(project_dir.resolve()),
        "apps": []
    }
    project.prepare_service_config()
    proj_db.insert(proj_data)

    project.connect()
    project.start()

    """



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


from .commands.routers import *
from .commands.projects import *
from .commands.apps import *


if __name__ == "__main__":
    app()
