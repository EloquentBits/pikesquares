import json
from ipaddress import IPv4Interface, IPv4Network
from pathlib import Path

import cuid
import structlog
from aiopath import AsyncPath

from pikesquares import get_first_available_port

#from pikesquares.domain.device import Device
from pikesquares.domain.project import Project
from pikesquares.domain.router import HttpRouter, TuntapDevice, TuntapRouter
from pikesquares.exceptions import StatsReadError
from pikesquares.presets.routers import HttpRouterSection
from pikesquares.service_layer.handlers.monitors import create_or_restart_instance
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()

#caddy_config_initial = """{"apps": {"http": {"https_port": 443, "servers": {"*.pikesquares.local": {"listen": [":443"], "routes": [{"match": [{"host": ["*.pikesquares.local"]}], "handle": [{"handler": "reverse_proxy", "transport": {"protocol": "http"}, "upstreams": [{"dial": "127.0.0.1:8035"}]}]}]}}}, "tls": {"automation": {"policies": [{"issuers": [{"module": "internal"}]}]}}}, "storage": {"module": "file_system", "root": "/var/lib/pikesquares/caddy"}}"""

caddy_config_initial = """
{
  "apps": {
    "http": {
      "https_port": 443,
      "servers": {

        "*.pikesquares.local": {
          "listen": [":443"],
          "routes": [
            {
              "match": [{"host": ["*.pikesquares.local"]}],
              "handle": [
                {
                  "handler": "reverse_proxy",
                  "transport": {"protocol": "http"},
                  "upstreams": [{"dial": "127.0.0.1:8035"}]
                }
              ]
            }
          ]
        }

      }
    },
    "tls": {
      "automation": {
        "policies": [
          {
            "issuers": [
              {
                "module": "internal"
              }
            ]
          }
        ]
      }
    }
  },
  "storage": {
    "module": "file_system",
    "root": "/var/lib/pikesquares/caddy"
  }
}"""


def edit_caddy_config(caddy_config_path: Path):

    with open(caddy_config_path, "r+") as caddy_config:

        vhost_key = "*.pikesquares.local"

        # data = json.load(caddy_config)
        #
        data = json.loads(caddy_config_initial)

        apps = data.get("apps")

        routes = apps.get("http").get("servers").get(vhost_key).get("routes")

        handles = routes[0].get("handle")

        upstreams = handles[0].get("upstreams")

        upstream_address = upstreams[0].get("dial")

        if upstream_address != f"{http_router_ip}:{http_router_port}":
            data["apps"]["http"]["servers"][vhost_key]["routes"][0]["handle"][0]["upstreams"][0][
                "dial"
            ] = f"{http_router_ip}:{http_router_port}"
            caddy_config.seek(0)
            json.dump(data, caddy_config)
            caddy_config.truncate()


async def provision_http_router(uow: UnitOfWork, project: Project, tuntap_router: TuntapRouter) -> HttpRouter:

    try:
        #http_router_ip = tuntap_router.ipv4_interface + 1
        http_router_ip = await tuntap_router_next_available_ip(tuntap_router)
        http_router = HttpRouter(
            service_id=f"http-router-{cuid.slug()}",
            run_as_uid="pikesquares",
            run_as_gid="pikesquares",
            project=project,
            uwsgi_plugins="tuntap" ,
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

async def tuntap_router_next_available_network(uow: UnitOfWork) -> IPv4Network:
    existing_networks = await get_tuntap_router_networks(uow) or []
    logger.debug(f"looking for available subnet for tuntap router. {len(existing_networks)} subnets exist in project")
    if existing_networks:
        #import ipdb;ipdb.set_trace()
        for i in range(100, 200):
            n = IPv4Network(f"192.168.{i}.0/24")
            if not any([not n.compare_networks(en) != 0 for en in existing_networks]):
                logger.debug(f"found a subnet {n} for new tuntap router")
                return n

    new_network = "192.168.100.0/24"
    logger.debug(f"choosing random subnet {new_network} for tuntap router")
    return IPv4Network(new_network) 

async def tuntap_router_next_available_ip(
    tuntap_router: TuntapRouter,
) -> IPv4Interface:

    device_ips = [d.ip for d in await tuntap_router.awaitable_attrs.tuntap_devices]
    if device_ips:
        max_ip = max(device_ips)
    else:
        max_ip = tuntap_router.ip
    return IPv4Interface(f"{max_ip}/{tuntap_router.netmask}") + 1


async def create_tuntap_router(
    uow: UnitOfWork,
    project: Project,
) -> TuntapRouter:

    try:
        new_network = await tuntap_router_next_available_network(uow)
        existing_networks = await get_tuntap_router_networks(uow) or []
        if any([not new_network.compare_networks(en) != 0 for en in existing_networks]):
            raise Exception(f"subnet {new_network} already taken ")

        try:
            # make tuntap router ip alwasys the first in the subnet
            ip = next(new_network.hosts())
        except StopIteration:
            pass
        else:
            service_slug = cuid.slug()
            tuntap_router = TuntapRouter(
                service_id=f"psq-{service_slug}" ,
                name=f"tuntap-{service_slug}",
                project=project,
                uwsgi_plugins="tuntap",
                ip=str(ip),
                netmask=str(new_network.netmask),
                data_dir=str(project.data_dir),
                config_dir=str(project.config_dir),
                log_dir=str(project.log_dir),
                run_dir=str(project.run_dir),
            )
            tuntap_router = await uow.tuntap_routers.add(tuntap_router)
            logger.info(f"created tuntap router with ip: {tuntap_router.ip}")
            return tuntap_router
    except Exception as exc:
        logger.error(f"unable to create tuntap router for project {project.service_id}")
        raise exc

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
        logger.error(f"unable to create tuntap device for service {linked_service_id}")
        raise exc

    return tuntap_device


async def http_router_up(
        uow: UnitOfWork,
        http_router: HttpRouter,
    ) -> bool:
    try:

        project = await http_router.awaitable_attrs.project
        tuntap_routers = await project.awaitable_attrs.tuntap_routers
        #await uow.tuntap_routers.get_by_project_id(project.id)
        tuntap_router = tuntap_routers[0]
        #http_router_iface = tuntap_router.ipv4_interface + 1
        #http_router_ip = str(http_router_iface.ip)
        #http_router_tuntap_device  = await uow.tuntap_devices.get_by_ip(http_router_ip)
        http_router_tuntap_device  = await uow.tuntap_devices.\
            get_by_linked_service_id(http_router.service_id)

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

        try:
            _ = HttpRouter.read_stats(http_router.stats_address)
            return True
        except StatsReadError:
            project_zmq_monitor = await project.awaitable_attrs.zmq_monitor
            project_zmq_monitor_address = project_zmq_monitor.zmq_address
            print(section.as_configuration().format())
            try:
                _ = Project.read_stats(project.stats_address)
                return True
            except StatsReadError:
                print(f"project is running. launching http router on {project_zmq_monitor_address}")

                assert await \
                    AsyncPath(project_zmq_monitor.socket_address).exists() and \
                    await AsyncPath(project_zmq_monitor.socket_address).is_socket(), f"{project_zmq_monitor_address} not available"

                await create_or_restart_instance(
                    project_zmq_monitor_address,
                    f"{http_router.service_id}.ini",
                    section.as_configuration().format(do_print=True),
                )
                return True

    except Exception as exc:
        raise
