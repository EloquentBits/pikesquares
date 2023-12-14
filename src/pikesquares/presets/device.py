from pathlib import Path

from . import (
    Section, 
)
from .routers import BaseRouterHttps
from ..conf import ClientConfig


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
        #self.run_httpsrouter()

    def run_httpsrouter(self):

        fw = self.routing.routers.https.forwarders.subscription_server(
            address=self.client_config.HTTPS_ROUTER_SUBSCRIPTION_SERVER
        )
        print(f"{self.client_config.CERT=}")
        print(f"{self.client_config.CERT_KEY=}")

        https_router = BaseRouterHttps(
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


