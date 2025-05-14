import structlog
from aiopath import AsyncPath
import cuid

from pikesquares import get_first_available_port
from pikesquares.domain.project import Project
from pikesquares.presets.project import ProjectSection
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.service_layer.handlers.monitors import create_zmq_monitor
from pikesquares.service_layer.handlers.routers import (
    create_http_router,
    create_tuntap_device,
    create_tuntap_router,
    get_tuntap_router_networks,
)
from pikesquares.service_layer.handlers.monitors import create_or_restart_instance

logger = structlog.getLogger()


async def create_project(
    name: str,
    context: dict,
    uow: UnitOfWork,
) -> Project | None:

    try:
        device = context.get("device")
        uwsgi_plugins = ["emperor_zeromq", "tuntap"]
        project = Project(
            service_id=f"proj-{cuid.slug()}",
            name=name,
            device=device,
            uwsgi_plugins=",".join(uwsgi_plugins),
            data_dir=str(device.data_dir),
            config_dir=str(device.config_dir),
            log_dir=str(device.log_dir),
            run_dir=str(device.run_dir),
        )
        project = await uow.projects.add(project)
        project_zmq_monitor = await create_zmq_monitor(uow, project=project)
        tuntap_router = await create_tuntap_router(uow, project)
        http_router = await create_http_router(uow, project, tuntap_router)

    except Exception as exc:
        raise exc

    # if project.enable_dir_monitor:
    #    if not await AsyncPath(project.apps_dir).exists():
    #        await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)
    #    uwsgi_config = project.write_uwsgi_config()
    #    logger.debug(f"wrote config to file: {uwsgi_config}")

    return project

async def up(uow, project, device_zmq_monitor):

    zmq_monitor = await uow.zmq_monitors.get_by_project_id(project.id)
    tuntap_router = await uow.tuntap_routers.get_by_project_id(project.id)

    section = ProjectSection(project)
    section.empire.set_emperor_params(
        vassals_home=zmq_monitor.uwsgi_zmq_address,
        name=f"{project.service_id}",
        stats_address=project.stats_address,
        spawn_asap=True,
        # pid_file=str((Path(conf.RUN_DIR) / f"{project.service_id}.pid").resolve()),
    )
    router_cls = section.routing.routers.tuntap
    router = router_cls(
        on=tuntap_router.socket_address,
        device=tuntap_router.name,
        stats_server=str(AsyncPath(
            tuntap_router.run_dir) / f"tuntap-{tuntap_router.name}-stats.sock"
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
    section.main_process.run_command_on_event(
        command="iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
        phase=section.main_process.phases.PRIV_DROP_PRE,
    )
    # enable linux ip forwarding
    section.main_process.run_command_on_event(
        command="echo 1 >/proc/sys/net/ipv4/ip_forward",
        phase=section.main_process.phases.PRIV_DROP_PRE,
    )
    section._set("emperor-use-clone", "net")

    print(section.as_configuration().format())
    await create_or_restart_instance(
        device_zmq_monitor.zmq_address,
        f"{project.service_id}.ini",
        section.as_configuration().format(do_print=True),
    )

