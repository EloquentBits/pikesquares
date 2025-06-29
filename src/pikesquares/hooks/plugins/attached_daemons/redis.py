from string import Template

import structlog
from aiopath import AsyncPath
from plumbum import ProcessExecutionError
from plumbum import local as pl_local

from pikesquares.domain.managed_services import AttachedDaemon
from pikesquares.hooks.markers import hook_impl

logger = structlog.getLogger()



class RedisAttachedDaemon:

    async def get_daemon_bin(self) -> AsyncPath:
        return AsyncPath("/usr/bin/redis-server")

    async def get_daemon_cli_bin(self) -> AsyncPath:
        return AsyncPath("/usr/bin/redis-cli")

    @hook_impl
    async def create_data_dir(self, service_name: str) -> bool | None:
        if service_name != "dnsmasq":
            return
        return True

    # get data dir
    #   redis-cli config get dir

    @hook_impl
    async def attached_daemon_collect_command_arguments(
        self,
        attached_daemon: AttachedDaemon,
        bind_ip: str,
        bind_port: int = 6379,
    ) -> dict | None:
        if attached_daemon.name != "redis":
            return

        cmd = Template(
            "$bin --pidfile $pidfile --logfile $logfile --dir $dir --bind $bind_ip --port $bind_port --daemonize no --protected-mode no"
        ).substitute({
            "bin" : str(await self.get_daemon_bin()),
            "bind_port": bind_port,
            "bind_ip": bind_ip,
            "dir": str(attached_daemon.daemon_data_dir),
            "logfile": str(
                AsyncPath(attached_daemon.log_dir) \
                / f"{attached_daemon.name}-server-{attached_daemon.service_id}.log"
            ),
            "pidfile": str(attached_daemon.pid_file),
        })
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

    @hook_impl
    async def attached_daemon_ping(
        self,
        attached_daemon: AttachedDaemon,
        bind_ip: str,
        bind_port: int = 6379,
    ) -> bool | None:
        """
            ping redis
        """
        if attached_daemon.name != "redis":
            return
        cmd_args = ["-h", bind_ip, "-p", bind_port, "--raw", "incr", "ping"]
        logger.info(cmd_args)
        try:
            with pl_local.cwd(attached_daemon.daemon_data_dir):
                retcode, stdout, stderr = pl_local[str(await self.get_daemon_cli_bin())].run(cmd_args)
                if int(retcode) != 0:
                    logger.debug(f"{retcode=}")
                    logger.debug(f"{stdout=}")
                    logger.debug(f"{stderr=}")
                    return False
                else:
                    return stdout.strip().isdigit()
        except ProcessExecutionError:
            raise

    @hook_impl
    async def attached_daemon_stop(
        self,
        attached_daemon: AttachedDaemon,
        bind_ip: str,
        bind_port: int = 6379,
    ) -> bool | None:
        """
           stop redis
        """
        if attached_daemon.name != "redis":
            return

        cmd_args = ["-h", bind_ip, "-p", bind_port, "shutdown"]
        if not await AsyncPath(attached_daemon.daemon_data_dir).exists():
            logger.info(f"{attached_daemon.service_id} data directory missing")
            return False
        try:
            with pl_local.cwd(attached_daemon.daemon_data_dir):
                retcode, stdout, stderr = pl_local[
                    str(self.get_daemon_cli_bin())
                ].run(cmd_args)

                if int(retcode) != 0:
                    logger.debug(f"{retcode=}")
                    logger.debug(f"{stdout=}")
                    logger.debug(f"{stderr=}")
                    return False
                else:
                    return stdout.strip().isdigit()
        except ProcessExecutionError as exc:
            raise exc

