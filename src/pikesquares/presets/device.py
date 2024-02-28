#from pathlib import Path

from . import (
    Section, 
)
#from .routers import BaseRouterHttps


class DeviceSection(Section):

    def __init__(self, svc_model):
        super().__init__(
            name="uwsgi",                                       # uwsgi: [uwsgi] section header
            strict_config=True,                                 # uwsgi: strict = true
        )
        self.svc_model = svc_model
        # env = project.env
        self.set_runtime_dir(str(svc_model.run_dir))

        # plugins = [
        #         "logfile",
        #         # "avahi",
        #         #"python",
        #         #"emperor_zmq",
        # ]
        # self.set_plugins_params(
        #     plugins=plugins,
        #     search_dirs=[conf.PLUGINS_DIR,],
        # )
        self.master_process.set_basic_params(
            enable=True,
            fifo_file = str(svc_model.fifo_file),
        )   # uwsgi: master = true
        self.main_process.set_basic_params(
            vacuum=True,
            # place here correct emperor wrapper
            #binary_path=str((Path(env.data_dir) / ".venv/bin/uwsgi").resolve())
        )
        self.main_process.set_owner_params(uid=svc_model.uid, gid=svc_model.gid)
        self.main_process.set_naming_params(
            prefix=f"[[ PikeSquares App ]] ",
            autonaming=True
        )
        #self.set_placeholder("vconf_run_dir", self.runtime_dir)
        #self.main_process.set_pid_file(
        #    str((Path(conf.RUN_DIR) / f"{self.service_id}.pid").resolve())
        #)
        
        if svc_model.conf.DAEMONIZE:
            self.main_process.daemonize(log_into=str(svc_model.log_file))

        self.main_process.set_basic_params(touch_reload=str(svc_model.touch_reload_file))

        self.networking.register_socket(
            self.networking.sockets.default(str(svc_model.socket_address))
        )
        #routers_dir = Path(self.conf.CONFIG_DIR) / "routers"
        #routers_dir.mkdir(parents=True, exist_ok=True)
        #empjs["uwsgi"]["emperor"] = str(routers_dir.resolve())

        self.empire.set_emperor_params(
            vassals_home = str(svc_model.apps_dir),
            #vassals_home = f"zmq://tcp://{svc_model.conf.EMPEROR_ZMQ_ADDRESS}",
            name=f"PikeSquares App",
            spawn_asap=True,
            stats_address=str(svc_model.stats_address),
            #str(Path(self._runtime_dir) / f"{svc_model.service_id}-stats.sock"),
            #pid_file=str((Path(conf.RUN_DIR) / f"{self.service_id}.pid").resolve()),
        )

        #"--emperor=zmq://tcp://127.0.0.1:5250",
        #self.empire.set_emperor_params(
        #    stats_address=str(Path(self._runtime_dir) / f"{self.service_id}-stats.sock")
        #)

        #uwsgiconf.options.spooler.Spooler
        self.spooler.set_basic_params(
            #touch_reload=str(""),
            quiet=False,
            process_count=1,
            max_tasks=10,
            harakiri=60,
            #change_dir=str(""),
            poll_interval=10,
            #cheap=True,
            #base_dir=str(""),
        )
        self.spooler.add(
            work_dir=str(svc_model.spooler_dir),
            external=False

        )

        self.caching.add_cache("pikesquares-settings", max_items=100)

        self.workers.set_mules_params(mules=3)

        #self.python.import_module(
        #    ["pikesquares.daemons.launch_standalone"], 
        #    shared=False,
        #)

        self.logging.add_logger(
            self.logging.loggers.file(filepath=str(svc_model.log_file))
        )
        self.logging.add_logger(self.logging.loggers.stdio())

        #self.run_fastrouter()
        #self.run_httpsrouter()


    def as_string(self):
        return self.as_configuration().print_ini()



    #def run_httpsrouter(self):
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

    #def run_fastrouter(self):
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

