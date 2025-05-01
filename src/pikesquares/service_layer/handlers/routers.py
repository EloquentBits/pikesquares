import structlog
from cuid import cuid

from pikesquares import get_first_available_port
from pikesquares import services
from pikesquares.domain.device import Device
from pikesquares.domain.router import BaseRouter
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def create_http_router(
    name: str,
    context: dict,
    uow: UnitOfWork,
) -> BaseRouter:

    device = context.get("device")
    http_router_port = get_first_available_port(port=8034)
    http_router_address = f"0.0.0.0:{http_router_port}"
    subscription_server_address = f"127.0.0.1:{get_first_available_port(port=5700)}"
    http_router = BaseRouter(
        service_id=f"http_router_{cuid()}",
        name=name,
        device=device,
        address=http_router_address,
        subscription_server_address=subscription_server_address,
        data_dir=str(device.data_dir),
        config_dir=str(device.config_dir),
        log_dir=str(device.log_dir),
        run_dir=str(device.run_dir),
    )
    try:
        logger.debug(f"adding {http_router} to {device}")
        await uow.routers.add(http_router)
        logger.debug(f"Created {http_router=}")

    except Exception as exc:
        logger.exception(exc)
        raise exc

    # if device.enable_dir_monitor:
    #    try:
    #        uwsgi_config = http_router.write_uwsgi_config()
    #    except PermissionError:
    #        logger.error("permission denied writing router uwsgi config to disk")
    #        logger.debug(f"wrote config to file: {uwsgi_config}")
    #    else:

    return http_router
