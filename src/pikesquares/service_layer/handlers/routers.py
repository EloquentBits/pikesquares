import structlog
import cuid
from aiopath import AsyncPath

from pikesquares.domain.device import Device
from pikesquares.domain.project import Project
from pikesquares.domain.router import HttpRouter, TuntapRouter, TuntapDevice
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def create_http_router(
    name: str,
    project: Project,
    uow: UnitOfWork,
    ip: str,
    port: int,
    subscription_server_address: str,
) -> HttpRouter:

    uwsgi_plugins = ["tuntap"]
    http_router = HttpRouter(
        service_id=f"http_router_{cuid.cuid()}",
        name=name,
        run_as_uid="pikesquares",
        run_as_gid="pikesquares",
        project=project,
        uwsgi_plugins=",".join(uwsgi_plugins),
        address=f"{ip}:{port}" ,
        subscription_server_address=subscription_server_address,
        data_dir=str(project.data_dir),
        config_dir=str(project.config_dir),
        log_dir=str(project.log_dir),
        run_dir=str(project.run_dir),
    )
    try:
        await uow.http_routers.add(http_router)
    except Exception as exc:
        raise exc

    return http_router


async def create_tuntap_router(
    project: Project,
    uow: UnitOfWork,
    ip: str,
    netmask: str,
    name: str | None = None,
) -> TuntapRouter:

    try:
        uwsgi_plugins = ["tuntap"]
        name = f"psq-{cuid.slug()}"
        service_id = f"tuntap_router_{cuid.cuid()}"
        tuntap_router = TuntapRouter(
            service_id=service_id,
            name=name,
            project=project,
            uwsgi_plugins=", ".join(uwsgi_plugins),
            socket=str(AsyncPath(project.run_dir) / f"{service_id}.sock"),
            ip=ip,
            netmask=netmask,
            data_dir=str(project.data_dir),
            config_dir=str(project.config_dir),
            log_dir=str(project.log_dir),
            run_dir=str(project.run_dir),
        )
        await uow.tuntap_routers.add(tuntap_router)
    except Exception as exc:
        raise exc

    return tuntap_router

async def create_tuntap_device(
    tuntap_router: TuntapRouter,
    uow: UnitOfWork,
    ip: str,
    netmask: str,
    name: str | None = None,
) -> TuntapDevice:

    try:
        name = name or f"tuntap-device-{cuid.slug()}"
        tuntap_device = TuntapDevice(
            name=name,
            ip=ip,
            netmask=netmask,
            tuntap_router=tuntap_router,
        )
        await uow.tuntap_devices.add(tuntap_device)
    except Exception as exc:
        raise exc

    return tuntap_device
