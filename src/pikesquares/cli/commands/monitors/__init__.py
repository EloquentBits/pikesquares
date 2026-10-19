import structlog
import typer

from pikesquares import services
from pikesquares.cli.console import console
from pikesquares.service_layer.handlers.monitors import get_or_create_zmq_monitor
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.get_logger()


# ALIASES = ("proj", "prj")
# HELP = f"""
#    Projects related commands.\n
#    Aliases: [i]{', '.join(ALIASES)}[/i]
# """

# proj_cmd = typer.Typer(no_args_is_help=True, rich_markup_mode="rich", name="projects", help=HELP)
# for alias in ALIASES:
#    app.add_typer(proj_cmd, name=alias, help=HELP, hidden=True)

app = typer.Typer()


@app.command(short_help="Create new moniror.\nAliases:[i] new")
@app.command(
    # "new", hidden=True
)
def create(
    ctx: typer.Context,
):
    """
    Create new imperial monitor

    Aliases: [i] create, new
    """
    context = ctx.ensure_object(dict)
    uow = services.get(context, UnitOfWork)

    monitor = get_or_create_zmq_monitor(context, project, uow)
    if monitor:
        console.success(f":heavy_check_mark:     Monitor '{monitor.uwsgi_zmq_address}' was successfully created!")
        uow = services.get(context, UnitOfWork)
    else:
        console.warning("Failed to create a Monitor")


@app.command(
    "monitors",
    rich_help_panel="Show",
    short_help="Show all monitors .\nAliases:[i] monitors, monitors list",
)
# @app.command("proj", rich_help_panel="Show", hidden=True)
@app.command("list")
def list_(ctx: typer.Context):
    """
    Show all monitors

    Aliases:[i] monitors, monitors list
    """
    context = ctx.ensure_object(dict)
    uow = services.get(context, UnitOfWork)
    device = context.get("device")
    if not device:
        console.warning("unable to lookup device")
        raise typer.Exit(0)

    projects = uow.projects.list()
    if not len(projects):
        console.warning("No projects were initialized, nothing to show!")
        raise typer.Exit()

    projects_out = []
    device_stats = device.stats()
    # import ipdb

    # ipdb.set_trace()
    if not device_stats:
        console.warning("unable to lookup project stats")
        raise typer.Exit(0)

    for project in projects:
        try:
            vassal_stats = next(filter(lambda v: v.id.split(".ini")[0], device_stats.vassals))
            projects_out.append(
                {
                    "name": project.name,
                    "status": "running" if vassal_stats else "stopped",
                    "id": project.service_id,
                }
            )
        except StopIteration:
            continue

    console.print_response(projects_out, title=f"Projects count: {len(projects)}", show_id=show_id)
