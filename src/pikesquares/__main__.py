"""PikeSquares entry point script."""

import asyncio

from pikesquares import cli, __app_name__


async def main():

    cli.app(prog_name=__app_name__)


if __name__ == "__main__":
    asyncio.run(main())

    # uvicorn.run(app, loop="uvloop")
