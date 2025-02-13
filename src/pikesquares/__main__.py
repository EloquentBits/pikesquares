"""PikeSquares entry point script."""

#from pathlib import Path
import logging
import json

import structlog

from pikesquares import cli, __app_name__


# Define a log file path
LOG_FILE = "app.log"

"""
# Custom file log processor
def write_to_file(logger, method_name, event_dict):
    with open(LOG_FILE, "a") as log_file:
        log_file.write(json.dumps(event_dict) + "\n")
    return event_dict  # Required by structlog's processor chain


# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),  # Add timestamp
        # structlog.processors.JSONRenderer(),  # Format as JSON
        write_to_file,  # Write to file
    ],
    context_class=dict,  # Use a standard dictionary for context
    logger_factory=structlog.PrintLoggerFactory(),  # PrintLoggerFactory is required but won't print due to write_to_file
    wrapper_class=structlog.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()
logger.info("This message will only be written to the log file", event="startup")
"""


"""
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.WriteLoggerFactory(
        file=Path("app").with_suffix(".log").open("wt")
    ),
)
"""

logger = structlog.get_logger()


def main():
    cli.app(prog_name=__app_name__)


if __name__ == "__main__":

    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logger.info("This message will only be written to the log file", event="startup")

    main()
