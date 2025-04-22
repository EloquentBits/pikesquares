from fastapi import APIRouter

from pikesquares.app.api.routes.services import (
    devices,
    # items,
    # login,
    # private,
    # users, 
    # utils
)
from pikesquares.conf import APISettings


api_router = APIRouter()

api_router.include_router(devices.router)
# api_router.include_router(login.router)
# api_router.include_router(users.router)
# api_router.include_router(utils.router)
# api_router.include_router(items.router)


# if settings.ENVIRONMENT == "local":
#    api_router.include_router(private.router)
