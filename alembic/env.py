from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection, make_url

from alembic import context
from pikesquares.conf import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Alembic uses a synchronous engine here, so strip the async driver from the
# application's URL (e.g. sqlite+aiosqlite:///... -> sqlite:///...).
db_url = make_url(settings.SQLALCHEMY_DATABASE_URI)
db_url = db_url.set(drivername=db_url.drivername.split("+", 1)[0])
config.set_main_option("sqlalchemy.url", db_url.render_as_string(hide_password=False))


# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from sqlmodel import SQLModel

from pikesquares.domain.base import (
    ServiceBase,
)
from pikesquares.domain.device import (
    Device,
    DeviceUWSGIOption,
)
from pikesquares.domain.managed_services import AttachedDaemon
from pikesquares.domain.monitors import DirMonitor, ZMQMonitor
from pikesquares.domain.project import Project
from pikesquares.domain.python_runtime import PythonAppRuntime
from pikesquares.domain.router import (
    HttpRouter,
    TuntapDevice,
    TuntapRouter,
)
from pikesquares.domain.runtime import (
    # AppCodebase,
    AppRuntime,
    PythonAppCodebase,
)
from pikesquares.domain.wsgi_app import WsgiApp

target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we create an Engine and associate a connection
    with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
