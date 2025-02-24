from typing import Any
from collections.abc import AsyncGenerator

import svcs
import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from sqlmodel import SQLModel

# from sqlmodel.ext.asyncio.session import AsyncSession

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


from pikesquares.app.api.main import api_router
from pikesquares.app.core.config import settings


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


# def create_sqlmodel_engine(settings: Settings, **kwargs):
#    return create_engine(settings.database_connection_str, **kwargs)

# def sqlmodel_session_maker(engine) -> Callable[[], Session]:
#    return lambda: Session(bind=engine, autocommit=False, autoflush=False)

# connect_args = {"check_same_thread": False}
# engine = create_engine(sqlite_url, connect_args=connect_args)

# engine = create_sqlmodel_engine(settings=settings, poolclass=StaticPool)
# SQLModel.metadata.create_all(engine)

# session_maker = sqlmodel_session_maker(engine)

# def get_db() -> AsyncGenerator[Session, None, None]:
#    with Session(engine) as session:
#        yield session
# SessionDep = Annotated[Session, Depends(get_db)]

# registry.register_factory(
#    Session,
#    get_db,
# )

async_engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, echo=True, future=True)
async_session = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, Any]:
    """Get a database session.

    To be used for dependency injection.
    """
    async with async_session() as session, session.begin():
        yield session


async def init_models() -> None:
    """Create tables if they don't already exist.

    In a real-life example we would use Alembic to manage migrations.
    """
    async with async_engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all)  # noqa: ERA001
        await conn.run_sync(SQLModel.metadata.create_all)


"""
async def init_db():
    async with async_engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

"""


async def get_session() -> AsyncSession:
    async_session = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@svcs.fastapi.lifespan
async def lifespan(
        app: FastAPI,
        registry: svcs.Registry,
    ):

    registry.register_factory(
        AsyncSession,
        get_session,
    )

    await init_models()

    yield {"your": "other", "initial": "state"}
    # Registry is closed automatically when the app is done.


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)


# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
