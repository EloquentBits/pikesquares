import structlog


from . import Section

# from .routers import BaseRouterHttps



logger = structlog.get_logger()


class DeviceSection(Section):

    def __init__(self, device):
        super().__init__(
            name="uwsgi",  # uwsgi: [uwsgi] section header
            strict_config=True,  # uwsgi: strict = true
            embedded_plugins=False,
        )
        self.device = device
        # env = project.env
        self.set_runtime_dir(str(device.run_dir))

        # base
        # = %(main_plugin)s,
        # ping, cache, nagios, rrdtool, carbon, rpc,
        # corerouter, fastrouter, http,
        # ugreen, signal, syslog, rsyslog,
        # logsocket,
        # router_uwsgi, router_redirect, router_basicauth,
        # zergpool, redislog, mongodblog,
        # router_rewrite, router_http,
        # logfile, router_cache, rawrouter, router_static, sslrouter,
        # spooler, cheaper_busyness, symcall,
        # transformation_tofile, transformation_gzip, transformation_chunked, transformation_offload,
        # router_memcached, router_redis, router_hash, router_expires, router_metrics,
        # transformation_template, stats_pusher_socket, router_fcgi

        # all
        # main_plugin = python,gevent,psgi,lua,php,rack,jvm,jwsgi,ring,mono,
        # transformation_toupper,coroae,v8,cgi,xslt,webdav,ssi,ldap,gccgo,rados,pypy,zabbix,curl_cron,tornado,
        # tuntap,pty,mongrel2,alarm_curl,router_radius,airbrake,gridfs
        for plugin in device.uwsgi_plugins.split(";"):
            self.set_plugins_params(
                plugins=plugin,
                search_dirs=[str(device.plugins_dir)],
                # autoload=True,
                # required=True,
            )
        self.print_plugins()

        self.master_process.set_basic_params(
            enable=True,
            no_orphans=True,
            fifo_file=str(device.master_fifo_file),
        )  # uwsgi: master = true
        self.main_process.set_basic_params(
            vacuum=True,
        )
        # binary_path = device.VIRTUAL_ENV / "bin/pyuwsgi"
        # print(f"{binary_path=}")
        # self.main_process.set_basic_params(
        #    binary_path=str(binary_path),
        # )
        # if os.environ.get("PEX_PYTHON_PATH"):
        #    self.main_process.set_basic_params(
        #        binary_path=os.environ.get("PEX_PYTHON_PATH"),
        #   place here correct emperor wrapper
        #   str((Path(env.data_dir) / ".venv/bin/uwsgi").resolve())
        #   )

        self.main_process.set_owner_params(
            uid=device.run_as_uid,
            gid=device.run_as_gid,
        )
        self.main_process.set_naming_params(
            prefix="[[ PikeSquares ]] ",
            suffix=f" [{device.service_id}]",
            name="PikeSquares Device ",
            autonaming=False,
        )
        # self.set_placeholder("vconf_run_dir", self.runtime_dir)
        self.main_process.set_pid_file(
            # str((Path(conf.run_dir) / f"{self.service_id}.pid").resolve())
            device.pid_file,
        )
        # if device.daemonize:
        #    self.main_process.daemonize(log_into=str(device.log_file))

        #self.main_process.set_basic_params(
        #    touch_reload=str(device.touch_reload_file),
        #)

        self.main_process.change_dir(to=device.data_dir)

        # self.main_process.run_command_on_event(
        #    command=f"chmod 664 {device.data_dir / 'pikesquares.db'}",
        #    phase=self.main_process.phases.PRIV_DROP_PRE,
        # )

        self.networking.register_socket(self.networking.sockets.default(str(device.socket_address)))

        # uwsgiconf.options.spooler.Spooler
        if 0:
            self.spooler.set_basic_params(
                # touch_reload=str(""),
                quiet=False,
                process_count=1,
                max_tasks=10,
                harakiri=60,
                # change_dir=str(device.DATA_DIR),
                poll_interval=10,
                # cheap=True,
                # base_dir=str(""),
            )
            self.spooler.add(work_dir=str(device.spooler_dir), external=False)

            self.caching.add_cache("pikesquares-settings", max_items=100)

        self.workers.set_basic_params(count=1)
        # self.workers.set_mules_params(mules=3)

        # self.python.import_module(
        #    ["pikesquares.daemons.launch_standalone"],
        #    shared=False,
        # )

        self.logging.add_logger(self.logging.loggers.stdio())
        self._set("show-config", "true")

        # self.logging.add_logger(
        #    self.logging.loggers.file(filepath=str(device.log_file))
        # )

        # self.run_fastrouter()
        # self.run_httpsrouter()

        """
        plugin = tuntap
        ; create the tun device 'emperor0' and bind it to a unix socket
        tuntap-router = emperor0 run/tuntap.socket
        tuntap-router-firewall-out = allow 192.168.0.0/24 192.168.0.1
        tuntap-router-firewall-out = deny 192.168.0.0/24 192.168.0.0/24
        tuntap-router-firewall-out = allow 192.168.0.0/24 0.0.0.0
        tuntap-router-firewall-out = deny
        tuntap-router-firewall-in = allow 192.168.0.1 192.168.0.0/24
        tuntap-router-firewall-in = deny 192.168.0.0/24 192.168.0.0/24
        tuntap-router-firewall-in = allow 0.0.0.0 192.168.0.0/24
        tuntap-router-firewall-in = deny

        ; give it an ip address
        exec-as-root = ifconfig emperor0 192.168.0.1 netmask 255.255.255.0 up
        ; setup nat
        exec-as-root = iptables -t nat -F
        exec-as-root = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
        ; enable linux ip forwarding
        exec-as-root = echo 1 >/proc/sys/net/ipv4/ip_forward
        ; force vassals to be created in a new network namespace
        emperor-use-clone = net
        """

    def as_string(self):
        return self.as_configuration().print_ini()

    # def run_httpsrouter(self):
    #    fw = self.routing.routers.https.forwarders.subscription_server(
    #        address=self.conf.HTTPS_ROUTER_SUBSCRIPTION_SERVER
    #    )
    #    print(f"{self.conf.CERT=}")
    #    print(f"{self.conf.CERT_KEY=}")

    #    https_router = BaseRouterHttps(
    #        on=self.conf.HTTPS_ROUTER,
    #        forward_to=fw,
    #        cert=self.conf.CERT,
    #        key=self.conf.CERT_KEY,
    #    )
    #    https_router.set_basic_params(
    #        stats_server=self.conf.HTTPS_ROUTER_STATS,
    #        quiet=False,
    #        keepalive=5,
    #        #resubscribe_addresses=resubscribe_to
    #    )
    #    https_router.set_connections_params(
    #        timeout_socket=500,
    #        timeout_headers=10,
    #        timeout_backend=60,
    #    )
    #    https_router.set_manage_params(
    #        chunked_input=True,
    #        rtsp=True,
    #        source_method=True
    #    )
    #    self.routing.use_router(https_router)

    # def run_fastrouter(self):
    #    """
    #    Run FastRouter for Device.
    #    """

    #    runtime_dir = self.get_runtime_dir()
    #    #resubscribe_bind_to = "" #127.0.0.1:3069"
    #    fastrouter_cls = self.routing.routers.fast
    #    fastrouter = fastrouter_cls(
    #        on=str(Path(runtime_dir) / "FastRouter.sock"),
    #        forward_to=fastrouter_cls.forwarders.subscription_server(
    #            address=str(Path(runtime_dir) / "SubscriptionServer.sock"),
    #        ),
    #    )
    #    fastrouter.set_basic_params(
    #        stats_server=str(Path(runtime_dir) / "FastRouter-stats.sock"),
    #        cheap_mode=True,
    #        quiet=False,
    #        buffer_size=8192,
    #        #gracetime=30,
    #    )
    #    fastrouter.set_connections_params(retry_delay=30)
    #    #if resubscribe_to and resubscribe_to not in subscription_server_address:
    #    fastrouter.set_resubscription_params(
    #        addresses=str(Path(runtime_dir) / f"SubscriptionServer.sock"),
    #        #bind_to=resubscribe_bind_to
    #    )
    #    fastrouter.set_owner_params(
    #        uid=self.conf.RUN_AS_UID,
    #        gid=self.conf.RUN_AS_GID,
    #    )
    #    self.routing.use_router(fastrouter)
