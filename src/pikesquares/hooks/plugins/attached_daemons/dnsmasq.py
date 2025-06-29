from string import Template

import structlog
from aiopath import AsyncPath

#from plumbum import ProcessExecutionError
#from plumbum import local as pl_local
from pikesquares.domain.managed_services import AttachedDaemon

#from pikesquares.service_layer.handlers.routers import http_router_ips
from pikesquares.hooks.markers import hook_impl

logger = structlog.getLogger()



class DnsmasqAttachedDaemon:

    async def get_daemon_bin(self) -> AsyncPath:
        return AsyncPath("/usr/sbin/dnsmasq")

    @hook_impl
    async def create_data_dir(self, service_name: str) -> bool | None:
        if service_name != "dnsmasq":
            return

        return False

    @hook_impl
    async def attached_daemon_collect_command_arguments(
            self,
            attached_daemon: AttachedDaemon,
            bind_ip: str,
            bind_port: int = 5353,
    ) -> dict | None:

        if attached_daemon.name != "dnsmasq":
            return

        cmd = Template(
            "$bin --bind-interfaces --conf-file=/dev/null --keep-in-foreground --log-queries --log-facility=$logfile --port=$bind_port --listen-address=$bind_ip --pid-file=$pidfile --no-resolv --user=pikesquares --group=pikesquares"
        ).substitute({
            "bin" : str(await self.get_daemon_bin()),
            "bind_port": str(bind_port),
            "bind_ip": bind_ip,
            "logfile": str(
                AsyncPath(attached_daemon.log_dir) \
                / f"{attached_daemon.name}-server-{attached_daemon.service_id}.log"
            ),
            "pidfile": str(attached_daemon.pid_file),
        })

        #http_router_addresses = await http_router_ips(uow)
        #if http_router_addresses:
        #    for addr in http_router_addresses:
        #        cmd = cmd + f" --address {addr}"
        logger.debug(cmd)

        return {
            "command": cmd,
            "for_legion": attached_daemon.for_legion,
            "broken_counter": attached_daemon.broken_counter,
            "pidfile": attached_daemon.pid_file,
            "control": attached_daemon.control,
            "daemonize": attached_daemon.daemonize,
            "touch_reload": str(attached_daemon.touch_reload_file),
            "signal_stop": attached_daemon.signal_stop,
            "signal_reload": attached_daemon.signal_reload,
            "honour_stdin": bool(attached_daemon.honour_stdin),
            "uid": attached_daemon.run_as_uid,
            "gid": attached_daemon.run_as_gid,
            "new_pid_ns": attached_daemon.new_pid_ns,
            "change_dir": str(attached_daemon.daemon_data_dir),
        }
