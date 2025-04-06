from cuid import cuid
import structlog

from pikesquares.domain.router import BaseRouter
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares import get_first_available_port


logger = structlog.getLogger()


async def get_or_create_http_router(
    name: str,
    device,
    uow: UnitOfWork,
    create_kwargs: dict,
) -> BaseRouter:

    http_router = await uow.routers.get_by_name(name)

    if not http_router:
        http_router_port = get_first_available_port(port=8034)
        http_router_address = f"0.0.0.0:{http_router_port}"
        subscription_server_address = f"127.0.0.1:{get_first_available_port(port=5700)}"
        http_router = BaseRouter(
            service_id=f"http_router_{cuid()}",
            name=name,
            device=device,
            address=http_router_address,
            subscription_server_address=subscription_server_address,
            **create_kwargs,
        )
        logger.debug(f"adding {http_router} to {device}")
        await uow.routers.add(http_router)
        await uow.commit()
        logger.debug(f"Created {http_router=}")

    if device.enable_dir_monitor:
        try:
            uwsgi_config = http_router.write_uwsgi_config()
        except PermissionError:
            logger.error("permission denied writing router uwsgi config to disk")
        else:
            logger.debug(f"wrote config to file: {uwsgi_config}")

    return http_router
