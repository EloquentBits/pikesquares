import typer

from typing import Optional, Tuple
from typing_extensions import Annotated

app = typer.Typer()

@app.command(short_help="Create new managed service\nAliases: [i] create, new")
@app.command()
def create(
    ctx: typer.Context,
    project: Optional[str] = typer.Option("", "--in", "--in-project", 
        help="Name or id of project to add new service to"
    ),
    name: Annotated[str, typer.Option("--name", "-n", help="service name")] = "",
    #source: Annotated[str, typer.Option("--source", "-s", help="app source")] = "",
    #app_type: Annotated[str, typer.Option("--app-type", "-t", help="app source")] =  "",
    #router_address: Annotated[str, typer.Option("--router-address", "-r", help="ssl router address")] =  "",

):
    """
    Create new managed service in project

    Aliases: [i] create, new
    """
    obj = ctx.ensure_object(dict)
    custom_style = obj.get("cli-style")
