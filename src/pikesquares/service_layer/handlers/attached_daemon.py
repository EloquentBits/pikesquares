import cuid
import structlog
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


async def up(uow, attached_daemon: AttachedDaemon):
    try:

        section = Section(
            name="uwsgi",
            runtime_dir="/var/run/pikesquares",
            project_name="redis-proj",
            strict_config=True,
            style_prints=True,
        )
        section.main_process.set_owner_params(uid="pikesquares", gid="pikesquares")
        section._set("jailed", "true")
        section._set("show-config", "true")
        section.set_plugins_params(
            plugins="tuntap",
            search_dirs=["/var/lib/pikesquares/plugins"],
        )
        section.monitoring.set_stats_params(
            address="/var/run/pikesquares/redis0-stats.sock"
        )
        section.master_process.set_basic_params(enable=True)
        section.master_process.set_exit_events(reload=True)
        section.networking.register_socket(
            section.networking.sockets.default("/var/run/pikesquares/redis0.sock")
        )
        section.logging.set_file_params(owner="true")
        section.logging.add_logger(
            section.logging.loggers.file(filepath="/var/log/pikesquares/redis0.log")
        )
        section.main_process.run_command_on_event(
            command="ifconfig lo up",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        section.main_process.run_command_on_event(
            command="ifconfig redis0 192.168.100.4 netmask 255.255.255.0 up",
            phase=section.main_process.phases.PRIV_DROP_PRE,
        )
        # and set the default gateway
        #exec-as-root = route add default gw 192.168.0.1
        section.main_process.run_command_on_event(
            command="route add default gw 192.168.100.1",
            phase=section.main_process.phases.PRIV_DROP_PRE
        )
        section.main_process.run_command_on_event(
            command="ping -c 1 192.168.100.1",
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

        router_tuntap = section.routing.routers.tuntap().\
            device_connect(
                device_name="redis0",
                socket="/var/run/pikesquares/psq-661z17r.sock",
            )
        section.routing.use_router(router_tuntap)

        pidfile = "/var/run/pikesquares/redis-server.pid"
        redis_bin = "/usr/bin/redis-server"
        redis_port = 6380
        redis_bind = "192.168.100.4"
        redis_dir = "/var/lib/pikesquares/redis0"
        redis_cmd = f"{redis_bin} --pidfile {pidfile} --logfile /var/log/pikesquares/redis-server.log --dir {redis_dir} --bind {redis_bind} --port {redis_port} --daemonize no"
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
            change_dir="/var/lib/pikesquares/redis",
        )
        await create_or_restart_instance(
            "ipc:///var/run/pikesquares/proj-5p0z1rj-zmq-monitor.sock",
            "redis0.ini",
            section.as_configuration().format(do_print=True),
        )

        try:
            _ = AttachedDaemon.read_stats(attached_daemon.stats_address)
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
            logger.info(f"launching project {attached_daemon.project.name} in {project_zmq_monitor_address}")
            try:
                _ = Project.read_stats(project.stats_address)
                return True
            except StatsReadError:
                print(f"project is running. launching http router on {project_zmq_monitor_address}")

                await create_or_restart_instance(
                    project_zmq_monitor_address,
                    f"{project.service_id}.ini",
                    section.as_configuration().format(do_print=True),
                )
    except Exception as exc:
        raise
