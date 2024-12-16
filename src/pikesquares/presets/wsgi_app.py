from pathlib import Path
from typing import Union

from uwsgiconf.typehints import Strlist

from . import Section
from ..services.data import VirtualHost, WsgiAppOptions


class BaseWsgiAppSection(Section):
    """Basic wsgi app configuration."""

    def __init__(
        self,
        name: str = None,
        *,
        touch_reload: Strlist = None,
        workers: int = 1,
        threads: Union[int, bool] = None,
        mules: int = 0,
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
        # self.main_process.set_basic_params(show_config=True)

        self.main_process.set_basic_params(vacuum=True)
        self.main_process.set_naming_params(
            autonaming=False,
            prefix=f"{process_prefix} " if process_prefix else None,
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

    def configure_owner(self, owner: str = "www-data"):
        """
        Shortcut to set process owner data.

        :param owner: Sets user and group. Default: ``www-data``. Also can be in format: `user:group`
        """
        if owner is not None:
            if ":" in owner:
                owner, group = owner.split(":")
                self.main_process.set_owner_params(uid=owner, gid=group)
            else:
                self.main_process.set_owner_params(uid=owner, gid=owner)
        return self

    #def set_domain_name(self, address: str, domain_name: str, 
    #                    socket_path: str = "", 
    #                    socket_addr: str = "",
    #                    plugin=None):
    #    """Sets domain name in config (by avahi or bonjour plugin).

    #    :param address: IP address to bind (provided in format IP:PORT)
    #    :param domain_name: Domain name which resolves IP address
    #    """
    #    if ":" in address:
    #        address, port = address.split(':')

    #    subscription_params = dict(
    #        server=self.conf.HTTPS_ROUTER_SUBSCRIPTION_SERVER,
    #        address=address,  # address and port of wsgi app
    #        key=domain_name  # <app_name>-<project_name>-vconf.local
    #    )
    #    subscription_params["address"] = socket_addr or socket_path

    #    print(f"{subscription_params=}")

    #    self.subscriptions.subscribe(**subscription_params)

    #    if plugin:
    #        self._set("plugin", plugin)
    #        self._set(f"bonjour-register", f"name={domain_name},ip={address}")
    #    return self


class WsgiAppSection(BaseWsgiAppSection):

    def __init__(
        self,
        svc_model,
        app_options: WsgiAppOptions,
        virtual_hosts: list[VirtualHost] = [],
    ):
        self.svc_model = svc_model
        self.virtual_hosts = virtual_hosts or []

        require_app = True
        embedded_plugins = self.embedded_plugins_presets.BASIC + ["python", "python2", "python3"]

        super().__init__(
            name="uwsgi",
            embedded_plugins=embedded_plugins,
            owner=f"{svc_model.conf.RUN_AS_UID}:{svc_model.conf.RUN_AS_GID}",
            touch_reload=svc_model.touch_reload_file,
            **app_options.model_dump(),
        )
        self.python.set_basic_params(
            enable_threads=True,
            # search_path=str(Path(self.project.pyvenv_dir) / 'lib/python3.10/site-packages'),
        )
        if app_options.pyvenv_dir:
            self.python.set_basic_params(
                python_home=app_options.pyvenv_dir,
            )

        self.main_process.change_dir(to=app_options.root_dir)
        self.main_process.set_pid_file(str(svc_model.pid_file))

        self.master_process.set_basic_params(
            enable=True,
            no_orphans=True,
            fifo_file=str(svc_model.fifo_file)
        )

        self.set_plugins_params(search_dirs=svc_model.conf.PLUGINS_DIR)

        # if app.wsgi_module and callable(app.wsgi_module):
        #    wsgi_callable = wsgi_module.__name__

        # self.set_plugins_params(
        #    plugins="python311",
        #    search_dirs=[conf.PLUGINS_DIR],
        # )

        # :param module:
        #    * load .wsgi file as the Python application
        #    * load a WSGI module as the application.
        #    .. note:: The module (sans ``.py``) must be importable, ie. be in ``PYTHONPATH``.
        #    Examples:
        #        * mypackage.my_wsgi_module -- read from `application` attr of mypackage/my_wsgi_module.py
        #        * mypackage.my_wsgi_module:my_app -- read from `my_app` attr of mypackage/my_wsgi_module.py
        # :param callable_name: Set WSGI callable name. Default: application.

        self.python.set_wsgi_params(
            module=str(app_options.wsgi_file),
            callable_name=app_options.wsgi_module
        )
        self.applications.set_basic_params(exit_if_none=require_app)

        self.networking.register_socket(
            self.networking.sockets.default(svc_model.socket_address)
        )

        # socket_path = str(Path(self.conf.RUN_DIR) / f"{service_id}.sock")

        # self.networking.register_socket(
        #    self.networking.sockets.default(socket_path)
        # )
        # self.subscriptions.subscribe(
        #     server=str(Path(self.conf.RUN_DIR) / f"SubscriptionServer-{project_id}.sock"),
        #     address=app_name,
        #     key=service_id
        # )

        # vhost_domain_name = f"{app_name}.{project_name}.vconf.local"

        # self.subscriptions.subscribe(
        #     server=self.conf.HTTPS_ROUTER_SUBSCRIPTION_SERVER,
        #     address="127.0.0.1:5500",  # <app_name>.<project_name>.vconf.local (forward from this address to https router)
        #     key=vhost_domain_name  # internal uwsgi key
        # )

        # enable the notification socket
        # notify-socket = /tmp/notify.socket
        # ; pass it in subscriptions
        # subscription-notify-socket = /tmp/notify.socket

        self.monitoring.set_stats_params(
            address=str(svc_model.stats_address)
        )
        # self.logging.add_logger(self.logging.loggers.stdio())
        self.logging.add_logger(
            self.logging.loggers.file(
                filepath=str(svc_model.log_file)
            )
        )

        # self.setup_virtual_hosts(virtual_hosts, socket_addr=socket_addr)

        # if ":" in address:
        #    address, port = address.split(':')

        # vhost = virtual_hosts[0]
        # vhost_router_cls = self.routing.routers.http
        # vhost_router_params = {}
        # if vhost.is_https:
        #    vhost_router_cls = RouterHttps
        #    vhost_router_params = {'cert': vhost.certificate_path, 'key': vhost.certificate_key}
        # vhost_router = vhost_router_cls(
        #    on=vhost.address,
        #    forward_to=socket_path,
        #    **vhost_router_params
        # )
        # self.routing.use_router(vhost_router)

        # if vhost.static_files_mapping:
        #    for mountpoint, target in vhost.static_files_mapping.items():
        #        self.statics.register_static_map(mountpoint, target)

        # for domain_name in vhost.server_names:
        #   self.set_domain_name(
        #    address=vhost.address,
        #    domain_name=name,
        #    socket_path=socket_path,
        #    socket_addr=socket_addr,
        # )
        #   subscribe2=key=test-wsgi-app.pikesquares.dev,server=127.0.0.1:5777

        # subscribe2=key=test-wsgi-app.pikesquares.dev,server=127.0.0.1:5777

        #  subscribe2=
        #            key=test-wsgi-app.pikesquares.dev,
        #            server=127.0.0.1:5777,
        #            sni_key=pikesquares.dev-key.pem,
        #            sni_crt=pikesquares.dev.pem,
        #            sni_ca=rootCA.pem

        for router in app_options.routers:
            self.subscriptions.subscribe(
                server=router.subscription_server_address,
                address=str(svc_model.socket_address),  # address and port of wsgi app
                key=router.subscription_server_key,
            )
            self.subscriptions.set_server_params(
               client_notify_address=svc_model.subscription_notify_socket,
            )

        # self.subscriptions.subscribe(
        #    {
        #        "server": subscription_server_address,
        #        "address": str(svc_model.socket_address),  # address and port of wsgi app
        #        "key": f"{svc_model.name}.pikesquares.dev{https_router_port}",
        #    }
        # )

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



    """
    def setup_virtual_hosts(self, virtual_hosts: list[VirtualHost], 
                            socket_path: str = "", socket_addr: str = ""):
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
                    socket_path=socket_path,
                    socket_addr=socket_addr,
                )
    """
