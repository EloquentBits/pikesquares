from typing import Dict, List, Type
from pathlib import Path
import json
from typing import Union

from uwsgiconf.config import (
    Section as _Section, 
    TypeSection, 
    Configuration as _Configuration,
)
from uwsgiconf.typehints import Strlist
from uwsgiconf.options.routing_routers import RouterHttp as _RouterHttp
from uwsgiconf.utils import filter_locals, KeyValue, listify
from uwsgiconf.formatters import (
    FORMATTERS, 
    FormatterBase, 
    ArgsFormatter,
    IniFormatter,
)

from ..conf import ClientConfig, VirtualHost


class JSONFormatter(FormatterBase):
    """Translates a configuration as JSON file."""

    alias: str = 'json'

    def format(self) -> str:
        config = {}
        for section_name, key, value in self.iter_options():
            if key == 'plugin':
                continue
            if not section_name in config:
                config[section_name] = {}
            if isinstance(key, tuple):
                _, key = key
            config[section_name][str(key)] =  str(value).strip()
        return json.dumps(config)

FORMATTERS: Dict[str, Type[FormatterBase]] = {formatter.alias: formatter for formatter in (
    ArgsFormatter,
    IniFormatter,
    JSONFormatter,
)}
"""Available formatters by alias."""
class Configuration(_Configuration):

    def format(self, *, do_print: bool = False, formatter: str = 'ini') -> Strlist:
        """Applies formatting to configuration.

        :param do_print: Whether to print out formatted config.
        :param formatter: Formatter alias to format options. Default: ini.

        """

        formatter = FORMATTERS[formatter]
        formatted = formatter(self.sections).format()

        if do_print:
            print(formatted)

        return formatted


class Section(_Section):

    def include(self, target: Union['Section', List['Section'], str, List[str]]) -> TypeSection:
        """Includes target contents into config.

        :param target: File path or Section to include.

        """
        for target_ in listify(target):
            if isinstance(target_, Section):
                target_ = ':' + target_.name
            self._set('ini', f"%s:{target_}", multi=True)

        return self


    def as_configuration(self, **kwargs) -> 'Configuration':
        """Returns configuration object including only one (this very) section.

        :param kwargs: Configuration objects initializer arguments.
        
        """
        return Configuration([self], **kwargs)


class RouterHttps(_RouterHttp):
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



class DeviceSection(Section):

    def __init__(
        self,
        client_config: ClientConfig,
        service_id: str,
    ):
        super().__init__(
            name="uwsgi",                                       # uwsgi: [uwsgi] section header
            strict_config=True,                                 # uwsgi: strict = true
        )
        self.service_id = service_id
        self.client_config = client_config
        # env = project.env
        self.set_runtime_dir(client_config.RUN_DIR)

        # plugins = [
        #         "logfile",
        #         # "avahi",
        #         #"python",
        #         #"emperor_zmq",
        # ]
        # self.set_plugins_params(
        #     plugins=plugins,
        #     search_dirs=[client_config.PLUGINS_DIR,],
        # )
        self.master_process.set_basic_params(
            enable=True,
            fifo_file = str(Path(self._runtime_dir) / f"{service_id}-master-fifo"),
        )   # uwsgi: master = true
        self.main_process.set_basic_params(
            vacuum=True,
            # place here correct emperor wrapper
            #binary_path=str((Path(env.data_dir) / ".venv/bin/uwsgi").resolve())
        )
        self.main_process.set_owner_params(uid=client_config.UID, gid=client_config.GID)

        #self.set_placeholder("vconf_run_dir", self.runtime_dir)
        self.main_process.set_pid_file(
            str((Path(client_config.RUN_DIR) / f"{self.service_id}.pid").resolve())
        )
        
        if self.client_config.DAEMONIZE:
            self.main_process.daemonize(
                log_into=str((Path(self.client_config.LOG_DIR) / f"{self.service_id}.log").resolve())
            )

        self.main_process.set_basic_params(
            touch_reload=str((Path(client_config.CONFIG_DIR) / f"{self.service_id}.json").resolve())
        )
        
        self.networking.register_socket(
            self.networking.sockets.default(str(Path(self._runtime_dir) / f"{service_id}.sock"))
        )

        self.empire.set_emperor_params(
            stats_address=str(Path(self._runtime_dir) / f"{service_id}-stats.sock")
        )

        #"--emperor=zmq://tcp://127.0.0.1:5250",
        #self.empire.set_emperor_params(
        #    stats_address=str(Path(self._runtime_dir) / f"{self.service_id}-stats.sock")
        #)

        self.caching.add_cache("pikesquares-settings", max_items=100)

        self.workers.set_mules_params(mules=3)

        #self.python.import_module(
        #    ["pikesquares.daemons.launch_standalone"], 
        #    shared=False,
        #)

        self.setup_loggers()

        #self.run_fastrouter()
        self.run_httpsrouter()

    def run_httpsrouter(self):

        fw = self.routing.routers.https.forwarders.subscription_server(
            address=self.client_config.HTTPS_ROUTER_SUBSCRIPTION_SERVER
        )
        print(f"{self.client_config.CERT=}")
        print(f"{self.client_config.CERT_KEY=}")

        https_router = RouterHttps(
            on=self.client_config.HTTPS_ROUTER,
            forward_to=fw,
            cert=self.client_config.CERT,
            key=self.client_config.CERT_KEY,
        )
        https_router.set_basic_params(
            stats_server=self.client_config.HTTPS_ROUTER_STATS,
            quiet=False,
            keepalive=5,
            #resubscribe_addresses=resubscribe_to
        )
        https_router.set_connections_params(
            timeout_socket=500,
            timeout_headers=10,
            timeout_backend=60,
        )
        https_router.set_manage_params(
            chunked_input=True,
            rtsp=True,
            source_method=True
        )
        self.routing.use_router(https_router)

    def run_fastrouter(self):
        """
        Run FastRouter for Device.
        """

        runtime_dir = self.get_runtime_dir()
        #resubscribe_bind_to = "" #127.0.0.1:3069"
        fastrouter_cls = self.routing.routers.fast
        fastrouter = fastrouter_cls(
            on=str(Path(runtime_dir) / "FastRouter.sock"),
            forward_to=fastrouter_cls.forwarders.subscription_server(
                address=str(Path(runtime_dir) / "SubscriptionServer.sock"),
            ),
        )
        fastrouter.set_basic_params(
            stats_server=str(Path(runtime_dir) / "FastRouter-stats.sock"),
            cheap_mode=True,
            quiet=False,
            buffer_size=8192,
            #gracetime=30,
        )
        fastrouter.set_connections_params(retry_delay=30)
        #if resubscribe_to and resubscribe_to not in subscription_server_address:
        fastrouter.set_resubscription_params(
            addresses=str(Path(runtime_dir) / f"SubscriptionServer.sock"),
            #bind_to=resubscribe_bind_to
        )
        fastrouter.set_owner_params(
            uid=self.client_config.UID, 
            gid=self.client_config.GID,
        )
        self.routing.use_router(fastrouter)

    def setup_loggers(self):
        self.logging.add_logger(
            self.logging.loggers.file(filepath=str(Path(self.client_config.LOG_DIR) / f"{self.service_id}.log"))
        )
        self.logging.add_logger(self.logging.loggers.stdio())

    def as_string(self):
        return self.as_configuration().print_ini()



class ProjectSection(Section):

    def __init__(
        self,
        client_config: ClientConfig,
        service_id: str,
    ):
        super().__init__(
            name="uwsgi",                                       # uwsgi: [uwsgi] section header
            strict_config=True,                                 # uwsgi: strict = true
        )
        self.service_id = service_id
        self.client_config = client_config
        # env = project.env
        self.set_runtime_dir(client_config.RUN_DIR)

        # plugins = [
        #         "logfile",
        #         #"python",
        #         "emperor_zmq",
        # ]
        # self.set_plugins_params(
        #     plugins=plugins,
        #     search_dirs=[client_config.PLUGINS_DIR],
        # )

        self.master_process.set_basic_params(
            enable=True,
            fifo_file = str(Path(self._runtime_dir) / f"{self.service_id}-master-fifo"),
        )   # uwsgi: master = true
        self.main_process.set_basic_params(
            vacuum=True,
            # place here correct emperor wrapper
            #binary_path=str((Path(env.data_dir) / ".venv/bin/uwsgi").resolve())
        )
        self.main_process.set_owner_params(uid=client_config.UID, gid=client_config.GID)

        self.main_process.set_pid_file(
            str((Path(client_config.RUN_DIR) / f"{self.service_id}.pid").resolve())
        )
        
        self.networking.register_socket(
            self.networking.sockets.default(str(Path(self._runtime_dir) / f"{self.service_id}.sock"))
        )

        self.empire.set_emperor_params(
            stats_address=str(Path(self._runtime_dir) / f"{self.service_id}-stats.sock")
        )

        self.setup_loggers()

        self.run_fastrouter()


    def as_string(self):
        return self.as_configuration().print_ini()

    def run_fastrouter(self):
        """
        Run fastrouter for Project.
        """

        runtime_dir = self.get_runtime_dir()
        #resubscribe_bind_to = "" #127.0.0.1:3069"
        fastrouter_cls = self.routing.routers.fast
        fastrouter = fastrouter_cls(
            on=str(Path(runtime_dir) / f"FastRouter-{self.service_id}.sock"),
            forward_to=fastrouter_cls.forwarders.subscription_server(
                address=str(Path(runtime_dir) / f"SubscriptionServer-{self.service_id}.sock"),
            ),
        )
        fastrouter.set_basic_params(
            stats_server=str(Path(runtime_dir) / f"FastRouter-{self.service_id}-stats.sock"),
            cheap_mode=True,
            quiet=False,
            buffer_size=8192,
            #gracetime=30,
        )
        fastrouter.set_connections_params(retry_delay=30)
        #if resubscribe_to and resubscribe_to not in subscription_server_address:
        fastrouter.set_resubscription_params(
            addresses=str(Path(runtime_dir) / f"SubscriptionServer.sock"),
            #bind_to=resubscribe_bind_to
        )
        fastrouter.set_owner_params(
            uid=self.client_config.UID, 
            gid=self.client_config.GID,
        )
        self.routing.use_router(fastrouter)

    def setup_loggers(self):
        self.logging.add_logger(self.logging.loggers.stdio())
        self.logging.add_logger(
            self.logging.loggers.file(filepath=str(Path(self.client_config.LOG_DIR) / f"{self.service_id}.log"))
        )


#def get_project_config(project_id, formatter="json"):

#    section = ProjectSection(
#        project_id=project_id,
#        run_dir=run_dir,
#        log_dir=log_dir,
#        uid=pwuid.pw_uid,
#        gid=pwuid.pw_gid,
#    )
#    configuration = section.as_configuration()
#    return configuration.format(formatter=formatter)


class Section(Section):
    """Basic wsgi app configuration."""

    def __init__(
        self,
        name: str = None,
        *,
        touch_reload: Strlist =None,
        workers: int = None,
        threads: Union[int, bool] = None,
        mules: int = None,
        owner: str = None,
        log_into: str = "",
        log_dedicated: bool = None,
        process_prefix: str = None,
        ignore_write_errors: bool = None,
        **kwargs
    ):
        """

        :param name: Section name.

        :param touch_reload: Reload uWSGI if the specified file or directory is modified/touched.

        :param workers: Spawn the specified number of workers (processes).
            Default: workers number equals to CPU count.

        :param threads: Number of threads per worker or ``True`` to enable user-made threads support.

        :param mules: Number of mules to spawn.

        :param owner: Set process owner user and group.

        :param log_into: Filepath or UDP address to send logs into.

        :param log_dedicated: If ``True`` all logging will be handled with a separate
            thread in master process.

        :param process_prefix: Add prefix to process names.

        :param ignore_write_errors: If ``True`` no annoying SIGPIPE/write/writev errors
            will be logged, and no related exceptions will be raised.

            .. note:: Usually such errors could be seen on client connection cancelling
               and are safe to ignore.

        :param kwargs:

        """
        super().__init__(strict_config=False, name=name, **kwargs)

        # Fix possible problems with non-ASCII.
        self.env('LANG', 'en_US.UTF-8')

        if touch_reload:
            self.main_process.set_basic_params(touch_reload=touch_reload)

        if workers:
            self.workers.set_basic_params(count=workers)
        else:
            self.workers.set_count_auto()

        set_threads = self.workers.set_thread_params

        if isinstance(threads, bool):
            set_threads(enable=threads)

        else:
            set_threads(count=threads)

        if log_dedicated:
            self.logging.set_master_logging_params(enable=True, dedicate_thread=True)

        self.workers.set_mules_params(mules=mules)
        self.workers.set_harakiri_params(verbose=True)

        # FIXME
        #self.main_process.set_basic_params(show_config=True)

        self.main_process.set_basic_params(vacuum=True)
        self.main_process.set_naming_params(
            autonaming=True,
            prefix=f'{process_prefix} ' if process_prefix else None,
        )
        self.master_process.set_basic_params(enable=True)
        self.master_process.set_exit_events(sig_term=True)  # Respect the convention. Make Upstart and Co happy.
        self.locks.set_basic_params(thunder_lock=True)
        self.configure_owner(owner=owner)
        if log_into:
            self.logging.log_into(target=log_into)

        if ignore_write_errors:
            self.master_process.set_exception_handling_params(no_write_exception=True)
            self.logging.set_filters(write_errors=False, sigpipe=False)


    def configure_owner(self, owner: str = 'www-data'):
        """
        Shortcut to set process owner data.

        :param owner: Sets user and group. Default: ``www-data``. Also can be in format: `user:group`
        """
        if owner is not None:
            if ':' in owner:
                owner, group = owner.split(':')
                self.main_process.set_owner_params(uid=owner, gid=group)
            else:
                self.main_process.set_owner_params(uid=owner, gid=owner)
        return self

    def set_domain_name(self, address: str, domain_name: str, socket_path: str = "", plugin=None):
        """Sets domain name in config (by avahi or bonjour plugin).

        :param address: IP address to bind (provided in format IP:PORT)
        :param domain_name: Domain name which resolves IP address
        """
        if ":" in address:
            address, port = address.split(':')

        subscription_params = dict(
            server=self.client_config.HTTPS_ROUTER_SUBSCRIPTION_SERVER,
            address=address,  # address and port of wsgi app
            key=domain_name  # <app_name>-<project_name>-vconf.local
        )
        if socket_path:
            subscription_params["address"] = socket_path

        self.subscriptions.subscribe(**subscription_params)

        if plugin:
            self._set("plugin", plugin)
            self._set(f"bonjour-register", f"name={domain_name},ip={address}")
        return self


class WsgiAppSection(Section):

    def __init__(
        self,
        service_id: str,
        client_config: ClientConfig,
        project_id: str,
        wsgi_file: str,
        pyvenv_dir: str,
        root_dir: str,
        wsgi_module: str = "",
        virtual_hosts: list[VirtualHost] = [],
        **kwargs
    ):
        self.service_id = service_id
        self.client_config = client_config
        self.virtual_hosts = virtual_hosts or []

        require_app = True
        embedded_plugins = self.embedded_plugins_presets.BASIC + ['python', 'python2', 'python3']

        owner = f"{client_config.UID}:{client_config.GID}"

        super().__init__(
            name='uwsgi', 
            embedded_plugins=embedded_plugins, 
            owner=owner,
            touch_reload=str(
                (Path(client_config.CONFIG_DIR) / f"{project_id}" / "apps" / f"{service_id}.json").resolve()
            ),
            **kwargs
        )
        self.python.set_basic_params(
            python_home=pyvenv_dir,
            enable_threads=True,
            #search_path=str(Path(self.project.pyvenv_dir) / 'lib/python3.10/site-packages'),
        )

        self.main_process.change_dir(to=str(Path(root_dir).resolve()))
        self.main_process.set_pid_file(
            str((Path(client_config.RUN_DIR) / f"{self.service_id}.pid").resolve())
        )

        self.master_process.set_basic_params( 
            enable=True,
            fifo_file=str(Path(client_config.RUN_DIR) / f"{service_id}-master-fifo"),
        )

        self.set_plugins_params(search_dirs=client_config.PLUGINS_DIR)

        #if app.wsgi_module and callable(app.wsgi_module):
        #    wsgi_callable = wsgi_module.__name__

        #self.set_plugins_params(
        #    plugins="python311",
        #    search_dirs=[client_config.PLUGINS_DIR],
        #)

        #:param module:
        #    * load .wsgi file as the Python application
        #    * load a WSGI module as the application.
        #    .. note:: The module (sans ``.py``) must be importable, ie. be in ``PYTHONPATH``.
        #    Examples:
        #        * mypackage.my_wsgi_module -- read from `application` attr of mypackage/my_wsgi_module.py
        #        * mypackage.my_wsgi_module:my_app -- read from `my_app` attr of mypackage/my_wsgi_module.py
        #:param callable_name: Set WSGI callable name. Default: application.

        self.python.set_wsgi_params(
            module=wsgi_file, 
            callable_name=wsgi_module if wsgi_module else None,
        )
        self.applications.set_basic_params(exit_if_none=require_app)

        socket_path = str(Path(self.client_config.RUN_DIR) / f"{service_id}.sock")
        self.networking.register_socket(
            #self.networking.sockets.http('127.0.0.1:8000'),
            self.networking.sockets.default(socket_path),
        )
        # self.subscriptions.subscribe(
        #     server=str(Path(self.client_config.RUN_DIR) / f"SubscriptionServer-{project_id}.sock"),
        #     address=app_name,
        #     key=service_id
        # )

        # vhost_domain_name = f"{app_name}.{project_name}.vconf.local"

        # self.subscriptions.subscribe(
        #     server=self.client_config.HTTPS_ROUTER_SUBSCRIPTION_SERVER,
        #     address="127.0.0.1:5500",  # <app_name>.<project_name>.vconf.local (forward from this address to https router)
        #     key=vhost_domain_name  # internal uwsgi key
        # )

        self.subscriptions.set_server_params(
            client_notify_address=str(Path(client_config.RUN_DIR) / f"{service_id}-notify.sock"),
        )

        self.monitoring.set_stats_params(
            address=str(Path(client_config.RUN_DIR) / f"{service_id}-stats.sock"),
        )
        
        self.setup_loggers()
        self.setup_virtual_hosts(virtual_hosts, socket_path)

        """
        vhost_address = ""
        domain_name = ""

        vhost_router_params = {
            'cert': "/home/pk/dev/eqb/vconf/ssl/conf.dev+4.pem",
            'key': "/home/pk/dev/eqb/vconf/ssl/conf.dev+4-key.pem",
        }
        vhost_router = self.routing.routers.https(
            on=vhost_address,
            forward_to=socket_path,
            **vhost_router_params
        )
        self.routing.use_router(vhost_router)

        #if vhost.static_files_mapping:
        #    for mountpoint, target in vhost.static_files_mapping.items():
        #        self.statics.register_static_map(mountpoint, target)
        
        self.set_domain_name(
            address=vhost_address,
            domain_name=domain_name
        )
        """


    def setup_loggers(self):
        # self.logging.add_logger(self.logging.loggers.stdio())
        self.logging.add_logger(
            self.logging.loggers.file(filepath=str(Path(self.client_config.LOG_DIR) / f"{self.service_id}.log"))
        )

    def setup_virtual_hosts(self, virtual_hosts: list[VirtualHost], socket_path: str):
        for vhost in virtual_hosts:
            #vhost_router_cls = self.routing.routers.http
            #vhost_router_params = {}
            #if vhost.is_https:
            #    vhost_router_cls = RouterHttps
            #    vhost_router_params = {'cert': vhost.certificate_path, 'key': vhost.certificate_key}
            #vhost_router = vhost_router_cls(
            #    on=vhost.address,
            #    forward_to=socket_path,
            #    **vhost_router_params
            #)
            #self.routing.use_router(vhost_router)

            if vhost.static_files_mapping:
                for mountpoint, target in vhost.static_files_mapping.items():
                    self.statics.register_static_map(mountpoint, target)
            
            for name in vhost.server_names:
                self.set_domain_name(
                    address=vhost.address,
                    domain_name=name,
                    socket_path=socket_path
                )



class HttpsRouterSection(Section):
    router_name = "[[ PikeSquares/HTTPS Router ]]"

    def __init__(
        self,
        name: str = "uwsgi",
        runtime_dir: str = None,
        project_name: str = None,
        address: str = "127.0.0.1:3017",
        stats_server_address: str = "127.0.0.1:9897",
        subscription_server_address: str = "127.0.0.1:5600",
        resubscribe_to: str = None,
        certificate_path: str = None,
        certificate_key: str = None,
        static_files_mapping: dict = None,
        **kwargs
    ):
        self.name = name
        self.runtime_dir = runtime_dir
        router_cls = self.routing.routers.https

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

        # host, port = address.split(':')
        # if host in ('0.0.0.0', '127.0.0.1'):
        #     address = f":{port}"
        
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
                address=subscription_server_address,
                key=subscription_server_address
            ),
            cert=certificate_path,
            key=certificate_key,
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
        
        if static_files_mapping:
            for mountpoint, target in static_files_mapping.items():
                self.statics.register_static_map(mountpoint, target)
    


class HttpRouterSection(Section):
    router_name = "[[ PikeSquares/HTTP Router ]]"

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
        static_files_mapping: dict = None,
        **kwargs,
    ):
        self.name = name
        self.runtime_dir = runtime_dir
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
        
        if static_files_mapping:
            for mountpoint, target in static_files_mapping.items():
                self.statics.register_static_map(mountpoint, target)



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


class ManagedServiceSection(Section):

    def __init__(self, client_config, project_id, service_id, command, pre_start_section=None, env_vars=None):
        super().__init__(
            name="uwsgi",
            runtime_dir=client_config.RUN_DIR,
            owner=f"{client_config.UID}:{client_config.GID}",
            touch_reload=str(
                (Path(client_config.CONFIG_DIR) / f"{project_id}" / "apps" / f"{service_id}.json").resolve()
            )
        )
        self.project_id = project_id
        self.service_id = service_id

        self.client_config = client_config

        if pre_start_section:
            self.include(pre_start_section)

        executable_path, *_ = command.split(' ')
        executable_name = Path(executable_path).stem
        pid_path = Path(client_config.RUN_DIR) / f"{executable_name}.pid"
        self.main_process.run_command_on_event(f"touch {pid_path}")

        if env_vars:
            self._setup_environment_variables(env_vars)

        self.master_process.attach_process_classic(
            f"{pid_path} {command}",
            background=True
            # pidfile=pid_path,
            # daemonize=True
        )

        self.monitoring.set_stats_params(
            address=str(Path(client_config.RUN_DIR) / f"{service_id}-stats.sock"),
        )
        self.setup_loggers()

    def setup_loggers(self):
        # self.logging.add_logger(self.logging.loggers.stdio())
        self.logging.add_logger(
            self.logging.loggers.file(filepath=str(Path(self.client_config.LOG_DIR) / f"{self.service_id}.log"))
        )

    def _setup_environment_variables(self, env_vars):
        for key, value in env_vars.items():
            self.env(key, value)



class CronJobSection(Section):

    def _setup_environment_variables(self, env_vars):
        for key, value in env_vars.items():
            self.env(key, value)

    def __init__(self, client_config, command, env_vars=None, **kwargs):
        super().__init__(
            name="uwsgi",
            runtime_dir=client_config.RUN_DIR,
            owner=f"{client_config.UID}:{client_config.GID}"
        )
        if env_vars is not None:
            self._setup_environment_variables(env_vars)

        # -15 -1 -1 -1 -1 - every 15 minute (minus X means */X, minus 1 means *)
        self.master_process.add_cron_task(
            command,
            **kwargs
        )
