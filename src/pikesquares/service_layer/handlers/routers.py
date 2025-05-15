from ipaddress import IPv4Interface, IPv4Address, IPv4Network
import structlog
import cuid
from aiopath import AsyncPath

from pikesquares import get_first_available_port
#from pikesquares.domain.device import Device
from pikesquares.domain.project import Project
#from pikesquares.domain.monitors import ZMQMonitor
from pikesquares.presets.routers import HttpRouterSection
from pikesquares.domain.router import HttpRouter, TuntapRouter, TuntapDevice
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.service_layer.handlers.monitors import create_or_restart_instance

logger = structlog.getLogger()


async def provision_http_router(uow: UnitOfWork, project: Project, tuntap_router: TuntapRouter) -> HttpRouter:

    try:
        http_router_ip = tuntap_router.ipv4_interface + 1
        uwsgi_plugins = ["tuntap"]
        http_router = HttpRouter(
            service_id=f"http-router-{cuid.slug()}",
            run_as_uid="pikesquares",
            run_as_gid="pikesquares",
            project=project,
            uwsgi_plugins=",".join(uwsgi_plugins),
            address=f"{str(http_router_ip.ip)}:{get_first_available_port(port=8034)}",
            data_dir=str(project.data_dir),
            config_dir=str(project.config_dir),
            log_dir=str(project.log_dir),
            run_dir=str(project.run_dir),
        )
        http_router = await uow.http_routers.add(http_router)
        http_router_tuntap_device = await create_tuntap_device(
            uow,
            tuntap_router,
            http_router_ip,
            http_router.service_id,
        )
    except Exception as exc:
        raise exc

    return http_router

async def get_tuntap_router_networks(uow: UnitOfWork):
    tuntap_routers = await uow.tuntap_routers.list()
    return [
        IPv4Interface(f"{router.ip}/{router.netmask}").network
        for router in tuntap_routers
    ]


async def create_tuntap_router(
    uow: UnitOfWork,
    project: Project,
) -> TuntapRouter | None:

    new_network = None
    tuntap_router = None
    try:
        existing_networks = await get_tuntap_router_networks(uow)
        for i in range(100, 200):
            n = IPv4Network(f"192.168.{i}.0/24")
            if not [n.compare_networks(en) != 0 for en in existing_networks]:
                new_network = n
                break
        if not new_network:
            raise Exception("unable to locate a free subnet for the tuntap router.")

        try:
            ip = next(new_network.hosts())
        except StopIteration:
            pass
        else:
            uwsgi_plugins = ["tuntap"]
            service_slug = cuid.slug()
            tuntap_router = TuntapRouter(
                service_id=f"psq-{service_slug}" ,
                name=f"tuntap-{service_slug}",
                project=project,
                uwsgi_plugins=", ".join(uwsgi_plugins),
                ip=str(ip),
                netmask=str(new_network.netmask),
                data_dir=str(project.data_dir),
                config_dir=str(project.config_dir),
                log_dir=str(project.log_dir),
                run_dir=str(project.run_dir),
            )
            tuntap_router = await uow.tuntap_routers.add(tuntap_router)
    except Exception as exc:
        raise exc

    return tuntap_router

async def create_tuntap_device(
    uow: UnitOfWork,
    tuntap_router: TuntapRouter,
    ip: IPv4Interface,
    linked_service_id: str,
) -> TuntapDevice:
    try:
        tuntap_device = TuntapDevice(
            name=f"psq-{cuid.slug()}" ,
            ip=str(ip.ip),
            netmask=str(tuntap_router.netmask),
            tuntap_router=tuntap_router,
            linked_service_id=linked_service_id,
        )
        await uow.tuntap_devices.add(tuntap_device)
    except Exception as exc:
        raise exc

    return tuntap_device


async def http_router_up(
        uow: UnitOfWork,
        project: Project,
        http_router: HttpRouter,
    ):

    tuntap_routers = await uow.tuntap_routers.get_by_project_id(project.id)
    tuntap_router = tuntap_routers[0]
    http_router_iface = tuntap_router.ipv4_interface + 1
    http_router_ip = str(http_router_iface.ip)

    http_router_tuntap_device  = await uow.tuntap_devices.get_by_ip(http_router_ip)
    assert http_router_tuntap_device, f"could not locate http router tuntap device [{http_router_ip}]"

    zmq_monitor = await uow.zmq_monitors.get_by_project_id(project.id)

    section = HttpRouterSection(http_router)
    section._set("jailed", "true")
    router_tuntap = section.routing.routers.tuntap().device_connect(
        device_name=http_router_tuntap_device.name,
        socket=tuntap_router.socket_address,
    )
    #.device_add_rule(
    #    direction="in",
    #    action="route",
    #    src=tuntap_router.ip,
    #    dst=http_router_tuntap_device.ip,
    #    target="10.20.30.40:5060",
    #)
    section.routing.use_router(router_tuntap)

    #; bring up loopback
    #exec-as-root = ifconfig lo up
    section.main_process.run_command_on_event(
        command="ifconfig lo up",
        phase=section.main_process.phases.PRIV_DROP_PRE,
    )
    # bring up interface uwsgi0
    #exec-as-root = ifconfig uwsgi0 192.168.0.2 netmask 255.255.255.0 up
    section.main_process.run_command_on_event(
        command=f"ifconfig {http_router_tuntap_device.name} {http_router_tuntap_device.ip} netmask {http_router_tuntap_device.netmask} up",
        phase=section.main_process.phases.PRIV_DROP_PRE,
    )
    # and set the default gateway
    #exec-as-root = route add default gw 192.168.0.1
    section.main_process.run_command_on_event(
        command=f"route add default gw {tuntap_router.ip}",
        phase=section.main_process.phases.PRIV_DROP_PRE
    )
    section.main_process.run_command_on_event(
        command=f"ping -c 1 {tuntap_router.ip}",
        phase=section.main_process.phases.PRIV_DROP_PRE,
    )

    print(section.as_configuration().format())

    await create_or_restart_instance(
        zmq_monitor.zmq_address,
        f"{http_router.service_id}.ini",
        section.as_configuration().format(do_print=True),
    )


