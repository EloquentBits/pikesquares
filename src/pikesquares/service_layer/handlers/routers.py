import structlog
import cuid
from aiopath import AsyncPath

from pikesquares.domain.router import HttpRouter, TuntapRouter, TuntapDevice
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def create_http_router(
    name: str,
    context: dict,
    uow: UnitOfWork,
    ip: str,
    port: int,
    subscription_server_address: str,
) -> HttpRouter:

    uwsgi_plugins = ["tuntap"]
    device = context.get("device")
    http_router = HttpRouter(
        service_id=f"http_router_{cuid.cuid()}",
        name=name,
        device=device,
        uwsgi_plugins=", ".join(uwsgi_plugins),
        address=f"{ip}:{port}" ,
        subscription_server_address=subscription_server_address,
        data_dir=str(device.data_dir),
        config_dir=str(device.config_dir),
        log_dir=str(device.log_dir),
        run_dir=str(device.run_dir),
    )
    try:
        await uow.routers.add(http_router)
    except Exception as exc:
        raise exc

    # if device.enable_dir_monitor:
    #    try:
    #        uwsgi_config = http_router.write_uwsgi_config()
    #    except PermissionError:
    #        logger.error("permission denied writing router uwsgi config to disk")
    #        logger.debug(f"wrote config to file: {uwsgi_config}")
    #    else:

    return http_router


async def create_tuntap_router(
    context: dict,
    uow: UnitOfWork,
    ip: str,
    netmask: str,
    name: str | None = None,
) -> TuntapRouter:

    uwsgi_plugins = ["tuntap"]
    device = context.get("device")
    name = f"psq-{cuid.slug()}"
    tuntap_router = TuntapRouter(
        service_id=f"tuntap_router_{cuid.cuid()}",
        name=name,
        device=device,
        uwsgi_plugins=", ".join(uwsgi_plugins),
        socket=str(AsyncPath(device.run_dir) / f"tuntap-{name}.sock"),
        ip=ip,
        netmask=netmask,
        data_dir=str(device.data_dir),
        config_dir=str(device.config_dir),
        log_dir=str(device.log_dir),
        run_dir=str(device.run_dir),
    )
    try:
        await uow.tuntap_routers.add(tuntap_router)
    except Exception as exc:
        raise exc

    # if device.enable_dir_monitor:
    #    try:
    #        uwsgi_config = http_router.write_uwsgi_config()
    #    except PermissionError:
    #        logger.error("permission denied writing router uwsgi config to disk")
    #        logger.debug(f"wrote config to file: {uwsgi_config}")
    #    else:

    return tuntap_router

async def create_tuntap_device(
    context: dict,
    tuntap_router: TuntapRouter,
    uow: UnitOfWork,
    ip: str,
    netmask: str,
    name: str | None = None,
) -> TuntapDevice:

    device = context.get("device")
    name = name or f"tuntap-device-{cuid.slug()}"
    tuntap_device = TuntapDevice(
        name=name,
        socket=str(AsyncPath(device.run_dir) / f"{name}.sock"),
        ip=ip,
        netmask=netmask,
        tuntap_router_id=tuntap_router.id,
        tuntap_router=tuntap_router,
    )
    try:
        await uow.tuntap_devices.add(tuntap_device)
    except Exception as exc:
        raise exc

    # if device.enable_dir_monitor:
    #    try:
    #        uwsgi_config = http_router.write_uwsgi_config()
    #    except PermissionError:
    #        logger.error("permission denied writing router uwsgi config to disk")
    #        logger.debug(f"wrote config to file: {uwsgi_config}")
    #    else:

    return tuntap_device
