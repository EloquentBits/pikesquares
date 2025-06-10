import cuid
import structlog
from aiopath import AsyncPath
import tenacity
import netifaces

from pikesquares.domain.device import Device
from pikesquares.domain.project import Project
from pikesquares.exceptions import StatsReadError
from pikesquares.presets.project import ProjectSection
from pikesquares.service_layer.handlers.monitors import create_or_restart_instance, create_zmq_monitor
from pikesquares.service_layer.handlers.routers import (
    create_tuntap_router,
    provision_http_router,
)
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def provision_project(
    name: str,
    device: Device,
    uow: UnitOfWork,
    selected_services: list[str] | None,
) -> Project | None:

    try:
        project = Project(
            service_id=f"proj-{cuid.slug()}",
            name=name,
            device=device,
            uwsgi_plugins="emperor_zeromq;tuntap",
            data_dir=str(device.data_dir),
            config_dir=str(device.config_dir),
            log_dir=str(device.log_dir),
            run_dir=str(device.run_dir),
        )
        project = await uow.projects.add(project)
        logger.info(f"created project {project}")

        if "zmq-monitor" in selected_services:
            logger.info(f"creating project zmq monitor in project {project.service_id}")
            project_zmq_monitor = await create_zmq_monitor(uow, project=project)
            logger.info(f"created project zmq monitor @ {project_zmq_monitor.socket_address}")

        if "tuntap-router" in selected_services:
            logger.info(f"creatint tuntap router for project {project.service_id}")
            tuntap_router = await create_tuntap_router(uow, project)
            logger.info(f"created tuntap router @ {tuntap_router.socket_address}")

        if "http-router" in selected_services:
            logger.info(f"creating http router for project {project.service_id}")
            http_router = await provision_http_router(uow, project, tuntap_router)
            logger.info(f"created http router @ {http_router.socket_address}")

        # if "dir-monitor" in selected_services:
        #    if not await AsyncPath(project.apps_dir).exists():
        #        await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)
        #    uwsgi_config = project.write_uwsgi_config()
        #    logger.debug(f"wrote config to file: {uwsgi_config}")

    except Exception as exc:
        logger.info(f"failed provisioning project {name}")
        raise exc


    return project

async def get_nat_interfaces() -> list[str]:

    PHYSICAL_PREFIXES = ('en', 'wl', 'et', 'ww') # https://www.freedesktop.org/software/systemd/man/latest/systemd.net-naming-scheme.html
    AF_LINK = 17  # MAC
    AF_INET = 2   # IPv4

    def is_physical(name: str) -> bool:
        return name.startswith(PHYSICAL_PREFIXES)

    nat_interfaces = []

    for iface in netifaces.interfaces():
        if not is_physical(iface):
            continue

        try:
            addr_info = netifaces.ifaddresses(iface)

            has_ipv4 = AF_INET in addr_info and any(
                'addr' in entry for entry in addr_info[AF_INET]
            )

            has_mac = AF_LINK in addr_info and any(
                'addr' in entry for entry in addr_info[AF_LINK]
            )

            if has_ipv4 and has_mac:
                nat_interfaces.append(iface)

        except Exception as e:
            logger.error(f"Error processing interface {iface}: {e}")

    return nat_interfaces

async def project_up(project)  -> bool:
    try:
        section = ProjectSection(project)

        project_zmq_monitor = await project.awaitable_attrs.zmq_monitor
        if project_zmq_monitor:
            section.empire.set_emperor_params(
                vassals_home=project_zmq_monitor.uwsgi_zmq_address,
                name=f"{project.service_id}",
                stats_address=project.stats_address,
                spawn_asap=True,
                # pid_file=str((Path(conf.RUN_DIR) / f"{project.service_id}.pid").resolve()),
            )
        for tuntap_router in await project.awaitable_attrs.tuntap_routers:
            router_cls = section.routing.routers.tuntap
            router = router_cls(
                on=str(tuntap_router.socket_address),
                device=tuntap_router.name,
                stats_server=str(AsyncPath(
                    tuntap_router.run_dir) / f"{tuntap_router.service_id}-stats.sock"
                ),
            )
            router.add_firewall_rule(direction="out", action="allow", src=str(tuntap_router.ipv4_network), dst=tuntap_router.ip)
            router.add_firewall_rule(direction="out", action="deny", src=str(tuntap_router.ipv4_network), dst=str(tuntap_router.ipv4_network))
            router.add_firewall_rule(direction="out", action="allow", src=str(tuntap_router.ipv4_network), dst="0.0.0.0")
            router.add_firewall_rule(direction="out", action="deny")
            router.add_firewall_rule(direction="in", action="allow", src=tuntap_router.ip, dst=str(tuntap_router.ipv4_network))
            router.add_firewall_rule(direction="in", action="deny", src=str(tuntap_router.ipv4_network), dst=str(tuntap_router.ipv4_network))
            router.add_firewall_rule(direction="in", action="allow", src="0.0.0.0", dst=str(tuntap_router.ipv4_network))
            router.add_firewall_rule(direction="in", action="deny")
            section.routing.use_router(router)

            # give it an ip address
            section.main_process.run_command_on_event(
                command=f"ifconfig {tuntap_router.name} {tuntap_router.ip} netmask {tuntap_router.netmask} up",
                phase=section.main_process.phases.PRIV_DROP_PRE,
            )
            # setup nat
            section.main_process.run_command_on_event(
                command="iptables -t nat -F", phase=section.main_process.phases.PRIV_DROP_PRE
            )
            nat_interfaces = await get_nat_interfaces()
            for nat_interface in nat_interfaces:
                section.main_process.run_command_on_event(
                    command=f"iptables -t nat -A POSTROUTING -o {nat_interface} -j MASQUERADE",
                    phase=section.main_process.phases.PRIV_DROP_PRE,
                )
        # enable linux ip forwarding
        section.main_process.run_command_on_event(
            command="echo 1 >/proc/sys/net/ipv4/ip_forward",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        # fs,pid,ipc,uts,net
        section._set("emperor-use-clone", "net")

        if 0:
            redis_tuntap_device = section.routing.routers.tuntap().\
                device_connect(
                    device_name="redis1",
                    socket="/var/run/pikesquares/psq-661z17r.sock",
                )
            section.routing.use_router(redis_tuntap_device)

            section.main_process.run_command_on_event(
                command="ifconfig redis1 192.168.100.5 netmask 255.255.255.0 up",
                phase=section.main_process.phases.PRIV_DROP_PRE,
            )
            #section.main_process.run_command_on_event(
            #    command="route add default gw 192.168.100.1",
            #    phase=section.main_process.phases.PRIV_DROP_PRE
            #)
            #section.main_process.run_command_on_event(
            #    command="ping -c 1 192.168.100.1",
            #    phase=section.main_process.phases.PRIV_DROP_PRE,
            #)
            #section.main_process.run_command_on_event(
            #    command="route -n",
            #    phase=section.main_process.phases.PRIV_DROP_PRE,
            #)
            #section.main_process.run_command_on_event(
            #    command="ping -c 1 8.8.8.8",
            #    phase=section.main_process.phases.PRIV_DROP_PRE,
            #)

        if 0:
            pidfile = "/var/run/pikesquares/redis1.pid"
            redis_dir = "/var/lib/pikesquares/redis1"
            redis_cmd = f"/usr/bin/redis-server --pidfile {pidfile} --logfile /var/log/pikesquares/redis1.log --dir {redis_dir} --bind 192.168.100.5 --port 6380 --daemonize no"
            section.master_process.attach_process(
                command=redis_cmd, #"/usr/bin/redis-server /etc/pikesquares/redis.conf",
                for_legion=False,
                broken_counter=3,
                pidfile=pidfile,
                control=False,
                daemonize=True,
                touch_reload="/etc/pikesquares/redis.conf",
                signal_stop=15,
                signal_reload=15,
                honour_stdin=0,
                uid="pikesquares",
                gid="pikesquares",
                new_pid_ns="false",
                change_dir=redis_dir,
            )
        #try:
        #    _ = await project.read_stats()
        #    logger.info(f"{project.name} [{project.service_id}]. is already running!")
        #    return True
        #except StatsReadError:
        #    print(section.as_configuration().format())

        device = await project.awaitable_attrs.device
        device_zmq_monitor = await device.awaitable_attrs.zmq_monitor
        device_zmq_monitor_address = device_zmq_monitor.zmq_address
        logger.info(f"launching project {project.name} {project.service_id} @ {device_zmq_monitor_address}")
        await create_or_restart_instance(
            device_zmq_monitor_address,
            f"{project.service_id}.ini",
            section.as_configuration().format(do_print=True),
        )
        try:
            stats = await project.read_stats()
        except tenacity.RetryError:
            logger.error(f"Unable to read stats {project.name}")
            return False 
        return True

    except Exception as exc:
        raise exc

async def project_delete(
    project: Project,
    uow: UnitOfWork,
)  -> bool:
    try:
        #project_zmq_monitor = await project.awaitable_attrs.zmq_monitor
        for tuntap_router in await project.awaitable_attrs.tuntap_routers:
            await uow.tuntap_routers.delete(tuntap_router.id)
            logger.info(f"deleted tuntap router {tuntap_router.service_id}")

        project_http_routers = await project.awaitable_attrs.http_routers
        for http_router in project_http_routers:
            await uow.http_routers.delete(http_router.id)
            logger.info(f"deleted http router {http_router.service_id}")

        await uow.projects.delete(project.id)
        logger.info(f"deleted project {project.name}")

    except Exception as exc:
        raise exc
