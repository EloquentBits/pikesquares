import logging
from typing import Any, Annotated
import contextlib
# from collections.abc import AsyncGenerator
# from typing import AsyncIterator

import svcs

import sentry_sdk
from fastapi import FastAPI, Depends, HTTPException
# from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from pikesquares.domain.device import Device, DeviceCreate

from pikesquares.app.api.main import api_router
from pikesquares.app.core.config import settings
from pikesquares.adapters.database import get_session
from pikesquares.service_layer.uow import UnitOfWork


logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


# def custom_generate_unique_id(route: APIRoute) -> str:
#    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


# SQLModel.metadata.create_all(engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # generate_unique_id_function=custom_generate_unique_id,
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


# DBSessionDep = Annotated[AsyncSession, Depends(get_session)]


@app.post("/devices", response_model=Device)
async def add_device(
        device: Device,
        # session: DBSessionDep,
        # db: AsyncSession = DBSessionDep,
        # services: svcs.fastapi.DepContainer,
    ):
    # logger.debug(session)
    # async_session = await services.aget(AsyncSession)
    # logger.debug(async_session)

    device = Device.model_validate(
       {"machineId": device.machine_id, "serviceId": device.service_id}
    )
    logger.debug(device.model_dump())

    # from pikesquares.adapters.database import sessionmanager

    _engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, **{"echo": True})
    _sessionmaker = async_sessionmaker(
        autocommit=False,
        bind=_engine,
        expire_on_commit=False
    )

    async with UnitOfWork(session_factory=_sessionmaker) as uow:
        await uow.devices.add(device)
        await uow.commit()

    return device

    """
    async with get_session() as session:
        # device = await Device.create(session, **device.dict())
        session.add(device)
        await session.commit()
        await session.refresh(device)
        logger.debug(device.model_dump())
        return device
    """


@app.get("/devices/{id}", response_model=Device)
async def read_device(
        # services: DepContainer,
        id: int,
    ) -> Any:
    """
    Get device by ID.
    """
    logger.debug(f"{settings.SQLALCHEMY_DATABASE_URI=}")
    logger.debug(f"reading device {id}")
    # session = services.get(AsyncSession)

    async with get_session() as session:
        #device = session.get(Device, id)

        statement = select(Device)
        results = await session.exec(statement)
        device = None
        for device in results:
            logger.debug(device)
        # logger.debug(device)

        #if not device:
        #    raise HTTPException(status_code=404, detail="Device not found")
        return device
