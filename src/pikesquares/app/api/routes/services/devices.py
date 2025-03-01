import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from svcs.fastapi import DepContainer

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from pikesquares.app.core.config import settings
from pikesquares.domain.device import Device
from pikesquares.adapters.database import get_session
from pikesquares.service_layer.uow import UnitOfWork

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


router = APIRouter(prefix="/devices", tags=["services"])


"""
@app.get("/ping")
async def pong():
    return {"ping": "pong!"}

@app.get("/songs", response_model=list[Song])
async def get_songs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Song))
    songs = result.scalars().all()
    return [Song(name=song.name, artist=song.artist, year=song.year, id=song.id) for song in songs]

@app.post("/songs")
async def add_song(song: SongCreate, session: AsyncSession = Depends(get_session)):
    song = Song(name=song.name, artist=song.artist, year=song.year)
    session.add(song)
    await session.commit()
    await session.refresh(song)
    return song
"""


# DBSessionDep = Annotated[AsyncSession, Depends(get_session)]
@router.post("/create", response_model=Device)
async def add_device(
        device: Device,
        services: DepContainer,
    ):
    session = await services.aget(AsyncSession)
    device = Device.model_validate(
       {"machineId": device.machine_id, "serviceId": device.service_id}
    )

    async with UnitOfWork(session=session) as uow:
        await uow.devices.add(device)
        await uow.commit()

    logger.debug(device.model_dump())
    return device


@router.get("/{id}", response_model=Device)
async def read_device(
        id: int,
        services: DepContainer,
    ) -> Any:
    """
    Get device by ID.
    """
    session = await services.aget(AsyncSession)

    async with UnitOfWork(session=session) as uow:
        return await uow.devices.get_by_id(id)

    # if not device:
    #    raise HTTPException(status_code=404, detail="Device not found")
