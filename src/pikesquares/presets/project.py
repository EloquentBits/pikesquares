from pathlib import Path

from . import Section



class ProjectSection(Section):

    def __init__(self, svc_model):
        super().__init__(
            name="uwsgi",                                       # uwsgi: [uwsgi] section header
            strict_config=True,                                 # uwsgi: strict = true
        )
        self.svc_model = svc_model

        self.set_runtime_dir(svc_model.client_config.RUN_DIR)

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
            fifo_file = str(Path(self._runtime_dir) / f"{svc_model.service_id}-master-fifo"),
        )   # uwsgi: master = true
        self.main_process.set_basic_params(
            vacuum=True,
            # place here correct emperor wrapper
            #binary_path=str((Path(self.client_config.DATA_DIR) / ".venv/bin/uwsgi").resolve())
        )
        self.main_process.set_owner_params(uid=svc_model.client_config.RUN_AS_UID, gid=svc_model.client_config.RUN_AS_GID)

        self.main_process.set_pid_file(
            str((Path(svc_model.client_config.RUN_DIR) / f"{svc_model.service_id}.pid").resolve())
        )
        
        self.networking.register_socket(
            self.networking.sockets.default(str(Path(self._runtime_dir) / f"{svc_model.service_id}.sock"))
        )

        self.empire.set_emperor_params(
            stats_address=str(Path(self._runtime_dir) / f"{svc_model.service_id}-stats.sock")
        )

        self.setup_loggers()
        #self.run_fastrouter()

    def as_string(self):
        return self.as_configuration().print_ini()

    """
    def run_fastrouter(self):
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
    """

    def setup_loggers(self):
        self.logging.add_logger(self.logging.loggers.stdio())
        self.logging.add_logger(
            self.logging.loggers.file(filepath=str(Path(self.svc_model.client_config.LOG_DIR) / f"{self.svc_model.service_id}.log"))
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


