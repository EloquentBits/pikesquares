from uwsgiconf.options.routing_routers import RouterHttp as _RouterHttp
from uwsgiconf.utils import filter_locals, KeyValue

from . import Section


class BaseRouterHttps(_RouterHttp):
    """uWSGI includes an HTTPS router/proxy/load-balancer that can forward requests to uWSGI workers.

    The server can be used in two ways:

        * embedded - automatically spawn workers and setup the communication socket
        * standalone - you have to specify the address of a uwsgi socket to connect to

            See `subscribe_to` argument to `.set_basic_params()`

    .. note:: If you want to go massive (virtualhosting and zero-conf scaling) combine the HTTP router
        with the uWSGI Subscription Server.

    """
    alias = 'http'  # Shares options with http.
    plugin = alias
    on_command = 'https2'

    def __init__(
            self, on, *, cert, key, forward_to=None, ciphers=None, client_ca=None, session_context=None, use_spdy=None,
            export_cert_var=None):
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
    router_name = "[[ Pike Squares App / HTTPS Router ]]"

    def __init__(self, svc_model, address: str, **kwargs):
        super().__init__(
            strict_config=True,
            name="uwsgi",
            runtime_dir=str(svc_model.run_dir),
            project_name=self.router_name,
            **kwargs,
        )
        self.svc_model = svc_model

        #self.service_id = service_id
        #self.conf = conf
        self.set_runtime_dir(str(self.svc_model.run_dir))

        #self.set_plugins_params(plugins="http")

        self.master_process.set_basic_params(enable=True)
        self.master_process.set_exit_events(reload=True)
        #self.main_process.set_basic_params(
        #    touch_reload="/srv/uwsgi/%n.http-router.ini"
        #)
        self.main_process.set_owner_params(uid=svc_model.uid, gid=svc_model.gid)
        self.main_process.set_naming_params(
            prefix=f"{self.router_name} {svc_model.service_id} ",
            autonaming=True
        )

        # host, port = address.split(':')
        # if host in ('0.0.0.0', '127.0.0.1'):
        #     address = f":{port}"
        
        #if resubscribe_to:
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
        #"https2": 
        #       "cert=/home/pk/dev/eqb/pikesquares/tmp/_wildcard.pikesquares.dev+2.pem,
        #       ciphers=HIGH,
        #       client_ca=/home/pk/.local/share/mkcert/rootCA.pem,
        #       key=/home/pk/dev/eqb/pikesquares/tmp/_wildcard.pikesquares.dev+2-key.pem,
        #       addr=127.0.0.1:3020",

        self.networking.register_socket(
            #self.networking.sockets.shared(address=str(svc_model.socket_address))
            self.networking.sockets.default(str(svc_model.socket_address))
        )
        # FIXME for when port is lower than the default on the cli
        ssl_context = address #f"={(int(address.split(':')[-1]) - 8443)}"
        self.router = BaseRouterHttps(
            ssl_context ,
            cert=str(svc_model.certificate),
            key=str(svc_model.certificate_key),
            forward_to=BaseRouterHttps.forwarders.subscription_server(
                address=str(svc_model.subscription_server_address),
                #key=subscription_server_address
            ),
            ciphers="HIGH",
            client_ca=str(svc_model.client_ca),
        )

        self.router.set_basic_params(
            stats_server=str(svc_model.stats_address),
            quiet=False,
            keepalive=5,
            #resubscribe_addresses=(svc_model.resubscribe_to),
        )
        self.router.set_connections_params(
            timeout_socket=500,
            timeout_headers=10,
            timeout_backend=60,
        )
        self.router.set_manage_params(
            chunked_input=True,
            rtsp=True,
            source_method=True
        )

        self.logging.set_file_params(owner="true")
        self.routing.use_router(self.router)

        #self.logging.log_into("%(emperor_logs_dir)/%n.http-router.log", before_priv_drop=False)
        self.logging.add_logger(
            self.logging.loggers.file(filepath=str(svc_model.log_file))
        )
        


class HttpRouterSection(Section):
    router_name = "[[ Pike Squares App / HTTP Router ]]"

    def __init__(
        self,
        name: str = "uwsgi",
        runtime_dir: str = None,
        # environment_name: str = None,
        project_name: str = None,
        address: str = "127.0.0.1:3017",
        stats_server_address: str = "127.0.0.1:9897",
        subscription_server_address: str = "127.0.0.1:5600",
        resubscribe_to: str = None,
        **kwargs,
    ):
        self.name = name
        #self.runtime_dir = runtime_dir
        self.set_runtime_dir(self.conf.RUN_DIR)
        router_cls = self.routing.routers.http

        super().__init__(
            strict_config=True,
            name=self.name,
            runtime_dir=self.runtime_dir,
            project_name=self.router_name,
            **kwargs,
        )

        self.set_plugins_params(plugins="http")

        self.master_process.set_basic_params(enable=True)
        self.master_process.set_exit_events(reload=True)
        self.main_process.set_basic_params(
            touch_reload="/srv/uwsgi/%n.http-router.ini"
        )
        self.main_process.set_owner_params(
            uid=kwargs.pop("uid", "%U"),
            gid=kwargs.pop("gid", "%G")
        )
        self.main_process.set_naming_params(
            prefix=f"{self.router_name} ",
            autonaming=True
        )

        host, port = address.split(':')
        if host in ('0.0.0.0', '127.0.0.1'):
            address = f":{port}"
        
        if resubscribe_to:
            address = "=0"
            self.networking.register_socket(
                self.networking.sockets.shared(
                    address="0.0.0.0:3435"
                )
            )

        self.router = router_cls(
            on=address,
            forward_to=router_cls.forwarders.subscription_server(
                address=subscription_server_address
            ),
        )

        self.router.set_basic_params(
            stats_server=stats_server_address,
            quiet=False,
            keepalive=5,
            resubscribe_addresses=resubscribe_to
        )
        self.router.set_connections_params(
            timeout_socket=500,
            timeout_headers=10,
            timeout_backend=60,
        )
        self.router.set_manage_params(
            chunked_input=True,
            rtsp=True,
            source_method=True
        )

        
        self.logging.set_file_params(owner="true")
        self.logging.log_into("%(emperor_logs_dir)/%n.http-router.log", before_priv_drop=False)
        self.routing.use_router(self.router)
        


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
