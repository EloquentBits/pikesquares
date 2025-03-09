import logging
from collections.abc import AsyncGenerator

import svcs
from svcs.fastapi import DepContainer

import sentry_sdk
from fastapi.responses import JSONResponse
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from pikesquares.app.api.main import api_router
from pikesquares.app.core.config import settings
from pikesquares.adapters.database import sessionmanager, get_session

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


# def custom_generate_unique_id(route: APIRoute) -> str:
#    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


@svcs.fastapi.lifespan
async def lifespan(
        app: FastAPI,
        registry: svcs.Registry,
    ) -> AsyncGenerator[dict[str, object], None]:

    registry.register_factory(AsyncSession, get_session)

    yield {"your": "other", "initial": "state"}


def create_db_and_tables():
    logger.debug("=== create_db_and_tables ===")
    SQLModel.metadata.create_all(sessionmanager._engine)


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)


@app.on_event("startup")
async def on_startup():
    # create_db_and_tables()
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

# @app.on_event('startup')
# def startup_event():
#    SQLModel.metadata.create_all(bind=engine)


@app.get("/healthy")
async def healthy(
        services: svcs.fastapi.DepContainer
    ) -> JSONResponse:
    ok: list[str] = []
    failing: dict[str, str] = {}
    code = 200

    # session = await services.aget(AsyncSession)

    for svc in services.get_pings():
        print(svc)
        try:
            await svc.aping()
            ok.append(svc.name)
        except Exception as e:
            failing[svc.name] = repr(e)
            code = 500

    return JSONResponse(
        content={"ok": ok, "failing": failing}, status_code=code
    )
