from pathlib import Path

import cuid
import structlog
from aiopath import AsyncPath
from uwsgiconf.config import Section

from pikesquares.domain.managed_services import AttachedDaemon
from pikesquares.domain.project import Project
from pikesquares.exceptions import StatsReadError
from pikesquares.service_layer.handlers.monitors import create_or_restart_instance
from pikesquares.service_layer.handlers.routers import create_tuntap_device, tuntap_router_next_available_ip
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def provision_attached_daemon(
    name: str,
    project: Project,
    uow: UnitOfWork,
) -> AttachedDaemon | None:

    try:
        daemons = await uow.attached_daemons.for_project_by_name(name, project.id)
        if not daemons:
            daemon = AttachedDaemon(
                service_id=f"{name}-{cuid.slug()}",
                name=name,
                run_as_uid="pikesquares",
                run_as_gid="pikesquares",
                project=project,
                uwsgi_plugins="tuntap",
                data_dir=str(project.data_dir),
                config_dir=str(project.config_dir),
                log_dir=str(project.log_dir),
                run_dir=str(project.run_dir),
            )
            daemon = await uow.attached_daemons.add(daemon)
            tuntap_routers = await uow.tuntap_routers.get_by_project_id(project.id)
            if tuntap_routers:
                ip = await tuntap_router_next_available_ip(tuntap_routers[0])
                await create_tuntap_device(uow, tuntap_routers[0], ip, daemon.service_id)
            return daemon

    except Exception as exc:
        raise exc

    return daemons[0]


async def attached_daemon_up(uow, attached_daemon: AttachedDaemon):
    try:
        project = await attached_daemon.awaitable_attrs.project
        tuntap_routers = await project.awaitable_attrs.tuntap_routers

        if not tuntap_routers:
            raise Exception(f"could not locate tuntap routers for project {project.name} [{project.id}]")

        tuntap_router  = tuntap_routers[0]
        attached_daemon_device = await uow.tuntap_devices.get_by_linked_service_id(attached_daemon.service_id)

        section = Section(
            name="uwsgi",
            runtime_dir=str(attached_daemon.run_dir),
            project_name=attached_daemon.name,
            strict_config=True,
            style_prints=True,
        )
        section.main_process.set_owner_params(
            uid=attached_daemon.run_as_uid,
            gid=attached_daemon.run_as_gid,
        )
        section.main_process.set_basic_params(
            touch_reload=str(attached_daemon.touch_reload_file),
        )
        section._set("jailed", "true")
        section._set("show-config", "true")
        section.set_plugins_params(
            plugins="tuntap",
            search_dirs=[str(attached_daemon.plugins_dir)],
        )
        section.monitoring.set_stats_params(
            address=str(attached_daemon.stats_address),
        )
        section.master_process.set_basic_params(enable=True)
        section.master_process.set_exit_events(reload=True)
        section.networking.register_socket(
            section.networking.sockets.default(str(attached_daemon.socket_address))
        )
        section.logging.set_file_params(owner="true")
        section.logging.add_logger(
            section.logging.loggers.file(filepath=str(attached_daemon.log_file))
        )
        router_tuntap = section.routing.routers.tuntap().\
            device_connect(
                device_name=f"{attached_daemon.name}",
                socket=tuntap_router.socket_address,
            )
        section.routing.use_router(router_tuntap)
        section.main_process.run_command_on_event(
            command="ifconfig lo up",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        section.main_process.run_command_on_event(
            command=f"ifconfig {attached_daemon.name} {attached_daemon_device.ip} netmask {attached_daemon_device.netmask} up",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        section.main_process.run_command_on_event(
            command=f"route add default gw {tuntap_router.ip}",
            phase=section.main_process.phases.PRIV_DROP_PRE
        )
        section.main_process.run_command_on_event(
            command=f"ping -c 1 {tuntap_router.ip}",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        section.main_process.run_command_on_event(
            command="route -n",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        section.main_process.run_command_on_event(
            command="ping -c 1 8.8.8.8",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        section.master_process.attach_process(
            **attached_daemon.collect_args(attached_daemon_device.ip)
        )
        try:
            _ = AttachedDaemon.read_stats(attached_daemon.stats_address)
            logger.info(f"Attached Daemon {attached_daemon.name} is already running")
        except StatsReadError:
            #console.success(f":heavy_check_mark:     Launching {attached_daemon.name}. Done!")
            print(section.as_configuration().format())
            #project_zmq_monitor = await project.awaitable_attrs.zmq_monitor
            #device = await project.awaitable_attrs.device
            project = await attached_daemon.awaitable_attrs.project
            project_zmq_monitor = await project.awaitable_attrs.zmq_monitor
            project_zmq_monitor_address = project_zmq_monitor.zmq_address
            #device_zmq_monitor = await device.awaitable_attrs.zmq_monitor
            #device_zmq_monitor_address = device_zmq_monitor.zmq_address
            logger.info(f"launching Attached Daemon {attached_daemon.name} @ {project_zmq_monitor_address}")
            try:
                _ = AttachedDaemon.read_stats(attached_daemon.stats_address)
                logger.info(f"Attached Daemon {attached_daemon.name} @ {project_zmq_monitor_address} is already running")
                return True
            except StatsReadError:
                logger.debug(f"project is running. launching attached daemon @ {project_zmq_monitor_address}")
                await create_or_restart_instance(
                    project_zmq_monitor_address,
                    f"{attached_daemon.service_id}.ini",
                    section.as_configuration().format(do_print=True),
                )
    except Exception as exc:
        raise
