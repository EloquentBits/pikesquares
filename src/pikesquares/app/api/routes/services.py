import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from svcs.fastapi import DepContainer

from pikesquares.domain.device import Device

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)



router = APIRouter(prefix="/services", tags=["services"])


@router.get("/devices/{id}", response_model=Device)
async def read_device(
        services: DepContainer,
        id: int,
    ) -> Any:
    """
    Get device by ID.
    """
    logger.debug(f"reading device {id}")
    session = services.get(AsyncSession)
    device = session.get(Device, id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/devices", response_model=Device)
async def add_device(
        device: Device,
        services: DepContainer,
    ):

    session = await services.aget(AsyncSession)
    # import pdb;pdb.set_trace()

    #with services.get(AsyncSession) as session:
    device = Device.model_validate(
            machine_id=device.machine_id,
            service_id=device.service_id,
    )
    session.add(device)
    await session.commit()
    await session.refresh(device)

    statement = select(Device).where(Device.machine_id == device.machine_id)
    dvc = await session.exec(statement).first()
    print(dvc)

    return device


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
