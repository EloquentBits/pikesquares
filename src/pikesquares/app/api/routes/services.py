import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from svcs.fastapi import DepContainer

# from pikesquares.app.api.deps import (
    # CurrentUser, 
    # SessionDep
# )
# from app.models import 
# Item,
# ItemCreate,
# ItemPublic,
# ItemsPublic,
# ItemUpdate,
# Message

from pikesquares.domain.device import Device


router = APIRouter(prefix="/services", tags=["services"])


@router.get("/{id}", response_model=Device)
async def read_device(
        services: DepContainer,
        id: uuid.UUID,
    ) -> Any:
    """
    Get device by ID.
    """
    session = services.get(AsyncSession)
    device = session.get(Device, id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device
