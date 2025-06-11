
import structlog
from ipaddress import IPv4Interface, IPv4Network
import netifaces

from pikesquares.service_layer.uow import UnitOfWork


logger = structlog.getLogger()


async def tuntap_router_next_available_ip(
    tuntap_router: "TuntapRouter",
) -> IPv4Interface:

    device_ips = [d.ip for d in await tuntap_router.awaitable_attrs.tuntap_devices]
    if device_ips:
        max_ip = max(device_ips)
    else:
        max_ip = tuntap_router.ip
    return IPv4Interface(f"{max_ip}/{tuntap_router.netmask}") + 1


async def get_tuntap_router_networks(uow: UnitOfWork):
    tuntap_routers = await uow.tuntap_routers.list()
    return [
        IPv4Interface(f"{router.ip}/{router.netmask}").network
        for router in tuntap_routers
    ]

async def range_free_ip(existing_networks: list[IPv4Network]) -> int:

    if existing_networks:
        return int(str(existing_networks[0]).split(".")[2])


    used_subnets = set()
    for iface in netifaces.interfaces():
        try:
            addrs = netifaces.ifaddresses(iface).get(netifaces.InterfaceType.AF_INET, [])
            for addr in addrs:
                ip = addr["addr"]
                netmask = addr.get("netmask", "255.255.255.0")
                network = IPv4Network(f"{ip}/{netmask}", strict=False)
                if str(network).startswith("172.28."):
                    used_subnets.add(network)
        except Exception as exc:
            logger.exception(exc)
            continue

    #import ipdb;ipdb.set_trace()
    for start in [1, 100, 200]:
        collision = False
        end = 100 if start == 1 else 200 if start == 100 else 256
        for i in range(start, end):
            n = IPv4Network(f"172.28.{i}.0/24")
            if any(n.overlaps(used) for used in used_subnets):
                collision = True
                break
        if not collision:
            return start

    raise RuntimeError("No available subnet range found (checked 172.28.1-255)")

async def tuntap_router_next_available_network(uow: UnitOfWork) -> IPv4Network:
    existing_networks = await get_tuntap_router_networks(uow) or []
    logger.debug(f"Looking for available subnet for tuntap router. "
                 f"{len(existing_networks)} existing subnets")

    start = await range_free_ip(existing_networks)
    end = min(start + 1, 256)
    for i in range(start, end):
        n = IPv4Network(f"172.28.{i}.0/24")

        #if not any([not n.compare_networks(en) != 0 for en in existing_networks]):
        #    logger.debug(f"found a subnet {n} for new tuntap router")

        if all(n != en for en in existing_networks):
            logger.debug(f"Found a subnet {n} for new tuntap router")
            return n

    raise RuntimeError("Unable to locate a free subnet for the tuntap router.")

