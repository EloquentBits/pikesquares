from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from svcs.fastapi import DepContainer

from pikesquares.domain.device import Device
from pikesquares.service_layer.uow import UnitOfWork

# logger = logging.getLogger("uvicorn.error")
# logger.setLevel(logging.DEBUG)

logger = structlog.getLogger()


router = APIRouter(prefix="/devices", tags=["services"])


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



@router.get("/{machine_id}", response_model=Device)
async def read_device(
        machine_id: str,
        services: DepContainer,
    ) -> Any:
    """
    Get device by machine id.
    """

    session = await services.aget(AsyncSession)

    async with UnitOfWork(session=session) as uow:
        device = await uow.devices.get_by_machine_id(machine_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return device

@router.put("/{machine_id}", response_model=Device)
async def update_device(
        machine_id: str,
        services: DepContainer,
        title: str
    ):
    """
    Update device by machine_id.
    """
    session = await services.aget(AsyncSession)

    async with UnitOfWork(session=session) as uow:
        device = await uow.devices.get_by_machine_id(machine_id)


)