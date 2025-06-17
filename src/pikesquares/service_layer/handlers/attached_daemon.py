import traceback
from pathlib import Path

import cuid
import structlog
import tenacity
import pluggy
from uwsgiconf.config import Section

from pikesquares.domain.managed_services import AttachedDaemon
from pikesquares.domain.project import Project
from pikesquares.service_layer.handlers.monitors import create_or_restart_instance, destroy_instance
from pikesquares.service_layer.handlers.routers import create_tuntap_device
from pikesquares.service_layer.ipaddress_utils import tuntap_router_next_available_ip
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def provision_attached_daemon(
    name: str,
    project: Project,
    uow: UnitOfWork,
    run_as_uid: str = "pikesquares",
    run_as_gid: str = "pikesquares",
) -> AttachedDaemon | None:

    daemon = None
    async with uow:
        try:
            daemons = await uow.attached_daemons.for_project_by_name(name, project.id)
            if daemons:
                return daemons[0]

            daemon = AttachedDaemon(
                service_id=f"{name}-{cuid.slug()}",
                name=name,
                run_as_uid=run_as_uid,
                run_as_gid=run_as_gid,
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

        except Exception as exc:
            logger.info(f"failed provisioning attached daemon {name}")
            logger.exception(exc)
            print(traceback.format_exc())
            await uow.rollback()
            raise exc

        await uow.commit()

    return daemon


async def attached_daemon_up(
    attached_daemon: AttachedDaemon,
    plugin_manager: pluggy.PluginManager,
    uow: "UnitOfWork",
    create_data_dir: bool = False
):
    try:
        project = await attached_daemon.awaitable_attrs.project
        tuntap_routers = await project.awaitable_attrs.tuntap_routers

        if not tuntap_routers:
            raise Exception(f"could not locate tuntap routers for project {project.name} [{project.id}]")

        tuntap_router  = tuntap_routers[0]
        attached_daemon_device = await uow.tuntap_devices.get_by_linked_service_id(attached_daemon.service_id)
        if not attached_daemon_device:
            raise Exception(f"could not locate tuntap device for attached daemon {attached_daemon.name} {attached_daemon.service_id}")

        cmd_args = plugin_manager.hook.attached_daemon_collect_command_arguments()
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
        if 0:
            section.main_process.set_basic_params(
                touch_reload=str(attached_daemon.touch_reload_file),
            )
        section._set("jailed", "true")
        section._set("show-config", "true")
        section.set_plugins_params(
            plugins="tuntap",
            search_dirs=[str(attached_daemon.plugins_dir)],
        )

        if create_data_dir:
            #section._set("if-not-dir", f"{attached_daemon.daemon_data_dir}")
            section.main_process.run_command_on_event(
                command=f"mkdir -p {attached_daemon.daemon_data_dir}",
                phase=section.main_process.phases.PRIV_DROP_POST,
            )
            section.main_process.run_command_on_event(
                command=f"chown {attached_daemon.run_as_uid}:{attached_daemon.run_as_uid} {attached_daemon.daemon_data_dir}",
                phase=section.main_process.phases.PRIV_DROP_POST,
            )
            #section._set("end-if", "")

        #section._set("if-not-file", f"{attached_daemon.touch_reload_file}")
        #section.main_process.run_command_on_event(
        #    command=f"touch {attached_daemon.touch_reload_file}",
        #    phase=section.main_process.phases.PRIV_DROP_POST,
        #)
        #section._set("end-if", "")

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
        # TODO
        # health check here?
        #section.master_process.add_cron_task

        # Attaches a command/daemon to the master process optionally managed by a pidfile.
        # This will allow the uWSGI master to control/monitor/respawn this process.
        #section.master_process.attach_process_classic

        if attached_daemon.name == "postgres":
            pg_bin_dir = Path("/usr/lib/postgresql/16/bin")
            pg_auth = "md5"
            section._set("if-not-dir", f"{attached_daemon.daemon_data_dir}")
            section.main_process.run_command_on_event(
                command=f"{pg_bin_dir / 'initdb'} --auth {pg_auth} --username pikesquares --pgdata {attached_daemon.daemon_data_dir} --encoding UTF-8",
                phase=section.main_process.phases.PRIV_DROP_POST,
            )
            section._set("end-if", "")

        section.master_process.attach_process(**cmd_args)
        try:
            _ = await attached_daemon.read_stats()
            logger.info(f"Attached Daemon {attached_daemon.name} is already running")
        except tenacity.RetryError:
            #print(section.as_configuration().format())
            project_zmq_monitor = await project.awaitable_attrs.zmq_monitor
            project_zmq_monitor_address = project_zmq_monitor.zmq_address
            logger.info(f"launching Attached Daemon {attached_daemon.name} @ {project_zmq_monitor_address}")
            await create_or_restart_instance(
                project_zmq_monitor_address,
                f"{attached_daemon.service_id}.ini",
                section.as_configuration().format(do_print=True),
                )
    except Exception as exc:
        raise exc

async def attached_daemon_down(
    attached_daemon: AttachedDaemon,
    plugin_manager: pluggy.PluginManager,
    uow: "UnitOfWork",
) -> bool:
    try:

        try:
            _ = await attached_daemon.read_stats()
        except tenacity.RetryError:
            logger.info(f"Managed service {attached_daemon.name} is not running")
            return False

        if plugin_manager.hook.attached_daemon_ping():
            logger.info(f"stopping {attached_daemon.name} [{attached_daemon.service_id}]")
            stop_result = plugin_manager.hook.stop()
            if stop_result:
                logger.info(f"stopped {attached_daemon.name} [{attached_daemon.service_id}]")
            else:
                logger.info(f"unable to stop {attached_daemon.name} [{attached_daemon.service_id}]")
        else:
            logger.info(f"daemon ping filed. not stopping {attached_daemon.name}")

        attached_daemon_device = await uow.tuntap_devices.\
            get_by_linked_service_id(attached_daemon.service_id)
        if not attached_daemon_device:
            raise Exception(f"could not locate tuntap device for attached daemon {attached_daemon.name} {attached_daemon.service_id}")

        project = await attached_daemon.awaitable_attrs.project
        project_zmq_monitor = await project.awaitable_attrs.zmq_monitor
        project_zmq_monitor_address = project_zmq_monitor.zmq_address
        logger.info(f"stopping attached daemon {attached_daemon.name} @ {project_zmq_monitor_address}")
        await destroy_instance(project_zmq_monitor_address, f"{attached_daemon.service_id}.ini")
        logger.info(f"stopped attached daemon {attached_daemon.name} @ {project_zmq_monitor_address}")

    except Exception as exc:
        raise exc

#/usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/pikesquares/attached-daemons/postgres-ne021zr stop
