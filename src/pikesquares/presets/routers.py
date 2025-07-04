import structlog

from aiopath import AsyncPath

from uwsgiconf.options.routing_routers import RouterHttp as _RouterHttp
from uwsgiconf.utils import filter_locals, KeyValue

from . import Section


logger = structlog.get_logger()


class RouterHttps(_RouterHttp):
    """uWSGI includes an HTTPS router/proxy/load-balancer that can forward requests to uWSGI workers.

    The server can be used in two ways:

        * embedded - automatically spawn workers and setup the communication socket
        * standalone - you have to specify the address of a uwsgi socket to connect to

            See `subscribe_to` argument to `.set_basic_params()`

    .. note:: If you want to go massive (virtualhosting and zero-conf scaling) combine the HTTP router
        with the uWSGI Subscription Server.

    """

    alias = "http"  # Shares options with http.
    plugin = alias
    on_command = "https2"

    def __init__(
        self,
        on,
        *,
        cert,
        key,
        forward_to=None,
        ciphers=None,
        client_ca=None,
        session_context=None,
        use_spdy=None,
        export_cert_var=None,
    ):
        """Binds https router to run on the given address.

        :param SocketShared|str on: Activates the router on the given address.

        :param str cert: Certificate file.

        :param str key: Private key file.

        :param str ciphers: Ciphers [alias] string.

            Example:
                * DEFAULT
                * HIGH
                * DHE, EDH

            * https://www.openssl.org/docs/man1.1.0/apps/ciphers.html

        :param str client_ca: Client CA file for client-based auth.

            .. note: You can prepend ! (exclamation mark) to make client certificate
                authentication mandatory.

        :param str session_context: Session context identifying string. Can be set to static shared value
            to avoid session rejection.

            Default: a value built from the HTTP server address.

            * http://uwsgi.readthedocs.io/en/latest/SSLScaling.html#setup-2-synchronize-caches-of-different-https-routers

        :param bool use_spdy: Use SPDY.

        :param bool export_cert_var: Export uwsgi variable `HTTPS_CC` containing the raw client certificate.

        """
        on = KeyValue(
            filter_locals(locals(), drop=['session_context', 'forward_to']),
            aliases={'on': 'addr', 'use_spdy': 'spdy'},
            bool_keys=['use_spdy'],
        )

        super().__init__(on, forward_to=forward_to)

        self._set_aliased('session-context', session_context)


class HttpsRouterSection(Section):
    router_name: str = "[[ PikeSquares  HTTPS Router ]] "

    def __init__(self, router, **kwargs):
        super().__init__(
            strict_config=True,
            name="uwsgi",
            **kwargs,
        )
        self.router = router

        self.set_runtime_dir(str(self.router.run_dir))

        for plugin in self.router.uwsgi_plugins.split(";"):
            self.set_plugins_params(
                plugins=plugin,
                search_dirs=[str(self.router.plugins_dir)],
            )
        if 0:
            self.print_plugins()

        self.master_process.set_basic_params(
            no_orphans=True,
            enable=True,
            fifo_file=str(self.router.master_fifo_file),
        )
        self.master_process.set_exit_events(reload=True)
        # self.main_process.set_basic_params(
        # touch_reload="/srv/uwsgi/%n.http-router.ini"
        #   touch_reload=str(self.router.touch_reload_file),
        # )
        self.main_process.set_owner_params(
            uid=self.router.run_as_uid,
            gid=self.router.run_as_gid,
        )
        self.main_process.set_naming_params(prefix=f"{self.router_name} {self.router.service_id} ", autonaming=True)

        # host, port = address.split(':')
        # if host in ('0.0.0.0', '127.0.0.1'):
        #     address = f":{port}"
        # if resubscribe_to:
        #    address = "=0"
        #    self.networking.register_socket(
        #        self.networking.sockets.shared(
        #            address="0.0.0.0:3435"
        #        )
        #    )

        # https = =0,
        #           ssl/test-gen/server.crt,
        #           ssl/test-gen/server.key,
        #           HIGH,
        #           ssl/test-gen/ca.crt
        # "https2":
        #       "cert=/home/pk/dev/eqb/pikesquares/tmp/_wildcard.pikesquares.dev+2.pem,
        #       ciphers=HIGH,
        #       client_ca=/home/pk/.local/share/mkcert/rootCA.pem,
        #       key=/home/pk/dev/eqb/pikesquares/tmp/_wildcard.pikesquares.dev+2-key.pem,
        #       addr=127.0.0.1:3020",

        self.networking.register_socket(
            # self.networking.sockets.shared(address=str(router.socket_address))
            self.networking.sockets.default(str(router.socket_address))
        )
        # FIXME for when port is lower than the default on the cli
        ssl_context = router.address  # f"={(int(address.split(':')[-1]) - 8443)}"
        self.router = RouterHttps(
            ssl_context,
            cert=str(router.certificate),
            key=str(router.certificate_key),
            forward_to=RouterHttps.forwarders.subscription_server(
                address=str(router.subscription_server_address),
                # key=subscription_server_address
            ),
            ciphers="HIGH",
            client_ca=str(router.certificate_ca),
        )

        self.router.set_basic_params(
            stats_server=str(router.stats_address),
            cheap_mode=True,
            quiet=False,
            keepalive=5,
            # resubscribe_addresses=(router.resubscribe_to),
        )
        self.router.set_connections_params(
            timeout_socket=500,
            timeout_headers=10,
            timeout_backend=60,
        )
        self.router.set_manage_params(chunked_input=True, rtsp=True, source_method=True)

        self.logging.set_file_params(owner="true")
        self.routing.use_router(self.router)

        # self.logging.log_into("%(emperor_logs_dir)/%n.http-router.log", before_priv_drop=False)
        self.logging.add_logger(self.logging.loggers.file(filepath=str(router.log_file)))


class HttpRouterSection(Section):
    router_name = "[[ PikeSquares  HTTP Router ]] "

    # def __init__(
    #    self,
    #    name: str = "uwsgi",
    #    runtime_dir: str = None,
    #    # environment_name: str = None,
    #    project_name: str = None,
    #    address: str = "127.0.0.1:3017",
    #    stats_server_address: str = "127.0.0.1:9897",
    #    subscription_server_address: str = "127.0.0.1:5600",
    #    resubscribe_to: str = None,
    #    **kwargs,
    # ):

    def __init__(self, router, **kwargs):
        # self.name = name
        # self.runtime_dir = runtime_dir
        # super().__init__(
        #    strict_config=True,
        #    name=self.name,
        #    runtime_dir=self.runtime_dir,
        #    project_name=self.router_name,
        #    **kwargs,
        # )

        super().__init__(strict_config=True, name="uwsgi", **kwargs)
        self.router = router

        self.set_runtime_dir(str(self.router.run_dir))

        for plugin in self.router.uwsgi_plugins.split(";"):
            self.set_plugins_params(
                plugins=plugin,
                search_dirs=[str(self.router.plugins_dir)],
            )

        if 0:
            self.print_plugins()

        self.master_process.set_basic_params(enable=True)
        self.master_process.set_exit_events(reload=True)

        # self.main_process.set_basic_params(
        # touch_reload="/srv/uwsgi/%n.http-router.ini"
        #    touch_reload=str(self.router.touch_reload_file),
        # )
        self.main_process.set_owner_params(uid=self.router.run_as_uid, gid=self.router.run_as_gid)
        self.main_process.set_naming_params(
            prefix="[[ PikeSquares HTTP Router ]] ",
            suffix=f" [{self.router.service_id}]",
            name=self.router_name,
            autonaming=False,
        )
        # host, port = address.split(':')
        # if host in ('0.0.0.0', '127.0.0.1'):
        #    address = f":{port}"

        # if resubscribe_to:
        #    address = "=0"
        #    self.networking.register_socket(
        #        self.networking.sockets.shared(
        #            address="0.0.0.0:3435"
        #        )
        #    )
        router_cls = self.routing.routers.http
        self.router = router_cls(
            on=router.address,
            forward_to=router_cls.forwarders.subscription_server(
                address=str(router.subscription_server_address),
            ),
        )

        self.router.set_basic_params(
            stats_server=str(router.stats_address),
            cheap_mode=True,
            quiet=False,
            keepalive=5,
            # resubscribe_addresses=resubscribe_to
        )
        self.router.set_connections_params(
            timeout_socket=500,
            timeout_headers=10,
            timeout_backend=60,
        )
        self.router.set_manage_params(chunked_input=True, rtsp=True, source_method=True)

        self.logging.set_file_params(owner="true")
        # self.logging.log_into("%(emperor_logs_dir)/%n.http-router.log", before_priv_drop=False)
        self.logging.add_logger(self.logging.loggers.file(filepath=str(router.log_file)))
        self.routing.use_router(self.router)
        self._set("show-config", "true")


"""
class FastRouterSection(Section):
    def __init__(
        self,
        name: str = "uwsgi",
        runtime_dir: str = None,
        environment_name: str = None,
        project_name: str = None,
        address: str = "127.0.0.1:3017",
        stats_server_address: str = "127.0.0.1:9897",
        subscription_server_address: str = "127.0.0.1:5600",
        resubscribe_to: str = None,
        resubscribe_bind_to: str = None,
        **kwargs,
    ):
        self.name = name
        self.runtime_dir = runtime_dir

        if project_name is None:
            fastrouter_name = environment_name
        else:
            fastrouter_name = f"{environment_name} - {project_name}"

        super().__init__(
            strict_config=True,
            name=self.name,
            runtime_dir=self.runtime_dir,
            project_name=fastrouter_name,
            **kwargs,
        )

        self.master_process.set_basic_params(enable=True)
        self.main_process.set_owner_params(uid=kwargs.get("uid"), gid=kwargs.get("gid"))
        self.main_process.set_naming_params(
            prefix=f"({project_name}) PikeSquares FastRouter Worker: ",
            name=f"({project_name}) PikeSquares FastRouter Master",
        )
        fastrouter_cls = self.routing.routers.fast
        fastrouter = fastrouter_cls(
            on=address,
            forward_to=fastrouter_cls.forwarders.subscription_server(
                address=subscription_server_address
            ),
        )
        fastrouter.set_basic_params(
            stats_server=stats_server_address,
            cheap_mode=True,
            quiet=False,
            buffer_size=8192,
        )
        fastrouter.set_connections_params(retry_delay=30)
        if resubscribe_to and resubscribe_to not in subscription_server_address:
            fastrouter.set_resubscription_params(
                addresses=resubscribe_to,
                bind_to=resubscribe_bind_to
            )
        self.routing.use_router(fastrouter)
"""
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


class TunTapRouterSection(Section):
    router_name = "[[ PikeSquares App / TunTtap Router ]]"

    # def __init__(
    #    self,
    #    name: str = "uwsgi",
    #    runtime_dir: str = None,
    #    # environment_name: str = None,
    #    project_name: str = None,
    #    address: str = "127.0.0.1:3017",
    #    stats_server_address: str = "127.0.0.1:9897",
    #    subscription_server_address: str = "127.0.0.1:5600",
    #    resubscribe_to: str = None,
    #    **kwargs,
    # ):

    def __init__(self, router, **kwargs):
        # self.name = name
        # self.runtime_dir = runtime_dir
        # super().__init__(
        #    strict_config=True,
        #    name=self.name,
        #    runtime_dir=self.runtime_dir,
        #    project_name=self.router_name,
        #    **kwargs,
        # )

        super().__init__(strict_config=True, name="uwsgi", **kwargs)
        self.router = router

        self.set_runtime_dir(str(self.router.run_dir))

        for plugin in self.router.uwsgi_plugins.split(";"):
            self.set_plugins_params(
                plugins=plugin,
                search_dirs=[str(self.router.plugins_dir)],
            )
        self.print_plugins()

        self.master_process.set_basic_params(enable=True)
        self.master_process.set_exit_events(reload=True)

        # self.main_process.set_basic_params(
        # touch_reload="/srv/uwsgi/%n.http-router.ini"
        #    touch_reload=str(self.router.touch_reload_file),
        # )
        self.main_process.set_owner_params(uid=self.router.run_as_uid, gid=self.router.run_as_gid)
        self.main_process.set_naming_params(prefix=f"{self.router_name} {self.router.service_id} ", autonaming=True)
        # host, port = address.split(':')
        # if host in ('0.0.0.0', '127.0.0.1'):
        #    address = f":{port}"

        # if resubscribe_to:
        #    address = "=0"
        #    self.networking.register_socket(
        #        self.networking.sockets.shared(
        #            address="0.0.0.0:3435"
        #        )
        #    )
        router_cls = self.routing.routers.tuntap
        self.router = router_cls(
            on=router.socket_address,
            device=router.name,
            stats_server=str(AsyncPath(self.router.run_dir) / f"tuntap-{router.name}-stats.sock"),
        )

        self.router.add_firewall_rule(direction="out", action="allow", src="192.168.34.0/24", dst=router.ip)
        self.router.add_firewall_rule(direction="out", action="deny", src="192.168.34.0/24", dst="192.168.34.0/24")
        self.router.add_firewall_rule(direction="out", action="allow", src="192.168.34.0/24", dst="0.0.0.0")
        self.router.add_firewall_rule(direction="out", action="deny")
        self.router.add_firewall_rule(direction="in", action="allow", src=router.ip, dst="192.168.34.0/24")
        self.router.add_firewall_rule(direction="in", action="deny", src="192.168.34.0/24", dst="192.168.34.0/24")
        self.router.add_firewall_rule(direction="in", action="allow", src="0.0.0.0", dst="192.168.34.0/24")
        self.router.add_firewall_rule(direction="in", action="deny")
        self.routing.use_router(self.router)

        # give it an ip address
        self.main_process.run_command_on_event(
            command=f"ifconfig {router.name} {router.ip} netmask {router.netmask} up",
            phase=self.main_process.phases.PRIV_DROP_PRE,
        )
        # setup nat
        self.main_process.run_command_on_event(
            command="iptables -t nat -F", phase=self.main_process.phases.PRIV_DROP_PRE
        )
        self.main_process.run_command_on_event(
            command="iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
            phase=self.main_process.phases.PRIV_DROP_PRE,
        )
        # enable linux ip forwarding
        self.main_process.run_command_on_event(
            command="echo 1 >/proc/sys/net/ipv4/ip_forward",
            phase=self.main_process.phases.PRIV_DROP_PRE,
        )
        # force vassals to be created in a new network namespace
        #section._set("emperor-use-clone", "net")

        self.logging.set_file_params(owner="true")
        # self.logging.log_into("%(emperor_logs_dir)/%n.http-router.log", before_priv_drop=False)
        self.logging.add_logger(self.logging.loggers.file(filepath=str(router.log_file)))

        self._set("show-config", "true")


"""
class FastRouterSection(Section):
    def __init__(
        self,
        name: str = "uwsgi",
        runtime_dir: str = None,
        environment_name: str = None,
        project_name: str = None,
        address: str = "127.0.0.1:3017",
        stats_server_address: str = "127.0.0.1:9897",
        subscription_server_address: str = "127.0.0.1:5600",
        resubscribe_to: str = None,
        resubscribe_bind_to: str = None,
        **kwargs,
    ):
        self.name = name
        self.runtime_dir = runtime_dir

        if project_name is None:
            fastrouter_name = environment_name
        else:
            fastrouter_name = f"{environment_name} - {project_name}"

        super().__init__(
            strict_config=True,
            name=self.name,
            runtime_dir=self.runtime_dir,
            project_name=fastrouter_name,
            **kwargs,
        )

        self.master_process.set_basic_params(enable=True)
        self.main_process.set_owner_params(uid=kwargs.get("uid"), gid=kwargs.get("gid"))
        self.main_process.set_naming_params(
            prefix=f"({project_name}) PikeSquares FastRouter Worker: ",
            name=f"({project_name}) PikeSquares FastRouter Master",
        )
        fastrouter_cls = self.routing.routers.fast
        fastrouter = fastrouter_cls(
            on=address,
            forward_to=fastrouter_cls.forwarders.subscription_server(
                address=subscription_server_address
            ),
        )
        fastrouter.set_basic_params(
            stats_server=stats_server_address,
            cheap_mode=True,
            quiet=False,
            buffer_size=8192,
        )
        fastrouter.set_connections_params(retry_delay=30)
        if resubscribe_to and resubscribe_to not in subscription_server_address:
            fastrouter.set_resubscription_params(
                addresses=resubscribe_to,
                bind_to=resubscribe_bind_to
            )
        self.routing.use_router(fastrouter)
"""
