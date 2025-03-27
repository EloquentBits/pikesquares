import logging
from collections.abc import AsyncGenerator

import svcs
import structlog

import sentry_sdk
from fastapi.responses import JSONResponse
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from asgi_lifespan import LifespanManager

from pikesquares.app.api.main import api_router
from pikesquares.app.core.config import settings
from pikesquares.adapters.database import DatabaseSessionManager
# from pikesquares.service_layer.uow import UnitOfWork

# logger = logging.getLogger("uvicorn.error")
# logger.setLevel(logging.DEBUG)

logger = structlog.get_logger()


# def custom_generate_unique_id(route: APIRoute) -> str:
#    return f"{route.tags[0]}-{route.name}"

logger.debug(f"{settings.SQLALCHEMY_DATABASE_URI=}")

if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

sessionmanager = DatabaseSessionManager(
    settings.SQLALCHEMY_DATABASE_URI, {"echo": True}
)


async def get_session() -> AsyncSession:
    async with sessionmanager.session() as session:
        return session


@svcs.fastapi.lifespan
async def lifespan(
        app: FastAPI,
        registry: svcs.Registry,
    ) -> AsyncGenerator[dict[str, object], None]:

    logger.debug("Starting up!")

    registry.register_factory(AsyncSession, get_session)

    # async def uow_factory():
    #    async with UnitOfWork(session=session) as uow:
    #        yield uow
    #services.register_factory(UnitOfWork, uow_factory)

    yield {"your": "other", "initial": "state"}

    logger.debug("Shutting down!")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)


@app.on_event("startup")
async def on_startup():
    if sessionmanager._engine:
        async with sessionmanager._engine.begin() as conn:
            await conn.run_sync(
                lambda conn: SQLModel.metadata.create_all(conn)
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

app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
)


@app.get("/healthy")
async def healthy(
        services: svcs.fastapi.DepContainer
    ) -> JSONResponse:
    ok: list[str] = []
    failing: dict[str, str] = {}
    code = 200

    # session = await services.aget(AsyncSession)
    """
    for svc in services.get_pings():
        logger.debug(svc)
        try:
            await svc.aping()
            ok.append(svc.name)
        except Exception as e:
            failing[svc.name] = repr(e)
            code = 500
    """

    return JSONResponse(
        content={"ok": ok, "failing": failing}, status_code=code
    )


# async def main():
#    async with LifespanManager(app) as manager:
#        logger.debug("We're in!")
#import asyncio; asyncio.run(main())


"""
from fastapi.concurrency import run_in_threadpool

@app.get("/")
async def call_my_sync_library():
    my_data = await service.get_my_data()

    client = SyncAPIClient()
    await run_in_threadpool(client.make_request, data=my_data)
"""
