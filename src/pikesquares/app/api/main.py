from fastapi import APIRouter

from pikesquares.app.api.routes import (
    services,
    # items,
    # login,
    # private,
    # users, 
    # utils
)
from pikesquares.app.core.config import settings

api_router = APIRouter()

api_router.include_router(services.router)
# api_router.include_router(login.router)
# api_router.include_router(users.router)
# api_router.include_router(utils.router)
# api_router.include_router(items.router)


# if settings.ENVIRONMENT == "local":
#    api_router.include_router(private.router)
