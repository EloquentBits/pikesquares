from pathlib import Path

import cuid
import structlog
import tenacity
from pluggy import PluginManager
from uwsgiconf.config import Section

from pikesquares.domain.managed_services import (
    AttachedDaemon,
    SimpleSocketAttachedDaemon,
    RedisAttachedDaemon,
    PostgresAttachedDaemon,
)
from pikesquares.domain.project import Project
from pikesquares.service_layer.handlers.monitors import create_or_restart_instance
from pikesquares.service_layer.handlers.routers import create_tuntap_device
from pikesquares.service_layer.ipaddress_utils import tuntap_router_next_available_ip
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def provision_attached_daemon(
    name: str,
    project: Project,
    uow: UnitOfWork,
    create_data_dir: bool = True
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
                create_data_dir=create_data_dir,
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


async def attached_daemon_up(
    uow,
    attached_daemon: AttachedDaemon,
    plugin_manager: PluginManager,
):
    try:

        project = await attached_daemon.awaitable_attrs.project
        tuntap_routers = await project.awaitable_attrs.tuntap_routers

        if not tuntap_routers:
            raise Exception(f"could not locate tuntap routers for project {project.name} [{project.id}]")

        tuntap_router  = tuntap_routers[0]
        attached_daemon_device = await uow.tuntap_devices.get_by_linked_service_id(attached_daemon.service_id)
        plugin_kwargs = {
            "daemon_service": attached_daemon,
            "bind_ip": str(attached_daemon_device.ip),
        }
        plugin_class = None
        if attached_daemon.name == "redis":
            plugin_class = RedisAttachedDaemon
        elif attached_daemon.name  == "postgres":
            plugin_class = PostgresAttachedDaemon
        elif attached_daemon.name  == "simple-socket":
            plugin_class = SimpleSocketAttachedDaemon

        if not plugin_class:
            raise Exception(f"unable to lookup plugin {attached_daemon.name}")

        plugin_manager.register(
            plugin_class(**plugin_kwargs)
        )
        #cmd_args = attached_daemon.compile_command_args(
        #    bind_ip or attached_daemon_device.ip,
        #    bind_port=bind_port,
        #)
        cmd_args = plugin_manager.hook.collect_command_arguments()
        # FIXME
        # why is this a list?
        if cmd_args and isinstance(cmd_args, list):
            cmd_args = cmd_args[0]

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
            print(section.as_configuration().format())
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
