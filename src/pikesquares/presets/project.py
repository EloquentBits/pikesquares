# from pathlib import Path
import structlog
from aiopath import AsyncPath

from . import Section

logger = structlog.get_logger()


class ProjectSection(Section):

    def __init__(self, project):
        super().__init__(
            name="uwsgi",  # uwsgi: [uwsgi] section header
            strict_config=True,  # uwsgi: strict = true
        )
        self.project = project

        self.set_runtime_dir(str(self.project.run_dir))

        self.set_plugins_params(
            plugins=self.project.uwsgi_plugins,
            search_dirs=[str(self.project.plugins_dir)],
        )
        self.print_plugins()

        self.master_process.set_basic_params(
            enable=True,
            no_orphans=True,
            fifo_file=str(AsyncPath(self.project.fifo_file)),
        )  # uwsgi: master = true
        self.main_process.set_basic_params(
            vacuum=True,
            # touch_reload=str((self.project.touch_reload_file)),
            # place here correct emperor wrapper
            # binary_path=str((Path(self.data_dir) / ".venv/bin/uwsgi").resolve())
            # binary_path=str((Path(self.project.VIRTUAL_ENV) / "bin/uwsgi").resolve())
        )
        self.main_process.set_owner_params(uid=self.project.run_as_uid, gid=self.project.run_as_gid)
        self.main_process.set_naming_params(
            prefix="[[ PikeSquares Project]] ",
            suffix=f" [{self.project.service_id}]",
            name=f"{self.project.name} ",
            autonaming=False,
        )

        self.main_process.set_pid_file(str(self.project.pid_file))

        self.networking.register_socket(self.networking.sockets.default(str(self.project.socket_address)))

        if 0:  # project.enable_dir_monitor:
            self.empire.set_emperor_params(
                vassals_home=project.apps_dir,
                name=f"PikeSquares Project {project.name}",
                stats_address=project.stats_address,
                spawn_asap=True,
                # pid_file=str((Path(conf.RUN_DIR) / f"{self.service_id}.pid").resolve()),
                # stats_address=str(Path(self._runtime_dir) / f"{project.service_id}-stats.sock")
            )
        if 0:  # project.zmq_monitor_address:
            self.empire.set_emperor_params(
                vassals_home=project.uwsgi_zmq_monitor_address,
                name=f"PikeSquares Project {project.name}",
                stats_address=project.stats_address,
                spawn_asap=True,
                # pid_file=str((Path(conf.RUN_DIR) / f"{self.service_id}.pid").resolve()),
            )

        # self.run_fastrouter()
        # self.logging.add_logger(self.logging.loggers.stdio())
        self.logging.add_logger(self.logging.loggers.file(filepath=str(self.project.log_file)))
        self._set("show-config", "true")

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
            uid=self.UID,
            gid=self.GID,
        )
        self.routing.use_router(fastrouter)
    """


# def get_project_config(project_id, formatter="json"):

#    section = ProjectSection(
#        project_id=project_id,
#        run_dir=run_dir,
#        log_dir=log_dir,
#        uid=pwuid.pw_uid,
#        gid=pwuid.pw_gid,
#    )
#    configuration = section.as_configuration()
#    return configuration.format(formatter=formatter)
