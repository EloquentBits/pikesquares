import json
from pathlib import Path
# from typing import NewType
# import shutil

# import zmq
from tinydb import Query
import pydantic

# from .. import get_service_status
# from .project import project_up
from pikesquares import get_first_available_port
from pikesquares.presets import Section
from pikesquares.services import register_factory
from ..presets import wsgi_app as wsgi_app_preset
from .data import VirtualHost, WsgiAppOptions
from pikesquares.services.base import BaseService


class WsgiApp(BaseService):

    config_section_class: Section = wsgi_app_preset.WsgiAppSection
    tiny_db_table: str = "wsgi-apps"

    # for k in config.keys():
    #    if k.endswith("_DIR"):
    #        dir = Path(config[k])
    #        if dir and not dir.exists():
    #            dir.mkdir(parents=True, exist_ok=True)

    # emperor_wrapper = Path(config.get("VENV_DIR", "")) / "bin/uwsgi"
    # if not emperor_wrapper.exists():
    #   parser.exit(1, message=f"unable to locate VConf binary wrapper @ {emperor_wrapper}.")
    #    return

    app_options: WsgiAppOptions

    virtual_hosts: list[VirtualHost] = []
    # zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / f"{self.app_options.project_id}" / "apps" / f"{self.service_id}.json"

    @pydantic.computed_field
    def touch_reload_file(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / f"{self.app_options.project_id}" / "apps" / f"{self.service_id}.json"

    @pydantic.computed_field
    def socket_address(self) -> str:
        return f"127.0.0.1:{get_first_available_port(port=4017)}"

    @pydantic.computed_field
    def subscription_notify_socket(self) -> Path:
        return Path(self.conf.RUN_DIR) / f"{self.service_id}-subscription-notify.sock"

    def zmq_up(self):
        # if not self.is_started() and str(self.service_config.resolve()).endswith(".stopped"):
        #    shutil.move(
        #        str(self.service_config),
        #        self.service_config.removesuffix(".stopped")
        #    )

        # if not get_service_status(self.project_id, self.conf) == "running":
        #    project = get_project(self.conf, self.project_id)
        #    if project:
        #        project_up(self.conf, project.get('name'), self.project_id)

        """
        if all([
            self.service_config,
            isinstance(self.service_config, Path),
            self.service_config.exists()]):
            msg = json.dumps(self.config_json).encode()
            #self.service_config.read_text()
            print(f"WSGI-App: TOUCH command {self.config_name} with config:\n{msg}")

            self.zmq_socket.send_multipart(
                [
                    b"touch",
                    self.config_name.encode(),
                    msg,
                ]
            )
        else:
            print("no service config.")
        """

    def save_config_to_tinydb(self, extra_data: dict = {}) -> None:
        super().save_config_to_tinydb(
            extra_data={"project_id": self.app_options.project_id}
        )

    def prepare_service_config(self):
        self.service_id = self.service_id
        self.prepare_virtual_hosts()

        # routers_db = self.db.table("routers")
        # router = routers_db.get(
        #    Query().service_id == self.wsgi_app_options.router_id
        # )
        # https_router_address = router.get("address")
        # subscription_server_address = router.get("service_config")["uwsgi"]["http-subscription-server"]
        # subscription_notify_socket = router.get("service_config")["uwsgi"]["notify-socket"]

        section = self.config_section_class(
            self,
            self.app_options,
            virtual_hosts=self.virtual_hosts,
        ).as_configuration().format(
            formatter="json",
            do_print=True,
        )

        self.config_json = json.loads(section)
        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["strict"] = True

        # print(self.config_json)
        # self.service_config.write_text(json.dumps(self.config_json))

    def prepare_virtual_hosts(self):
        server_names = [
                f"{self.name}.pikesquares.dev",
        ]
        self.virtual_hosts = [
            VirtualHost(
                address=self.socket_address,
                certificate_path=str(self.certificate),
                certificate_key=str(self.certificate_key),
                server_names=[sn for sn in server_names if "--" not in sn]
            )
        ]

    def zmq_connect(self):
        pass
        # emperor_zmq_opt = uwsgi.opt.get('emperor', b'').decode()
        # zmq_port = emperor_zmq_opt.split(":")[-1]
        # zmq_port = "5500"
        # self.zmq_socket.connect(f'tcp://127.0.0.1:{zmq_port}')

    def start(self):
        pass

    def stop(self):
        pass
        # if self.service_config is None:
        #    self.service_config = Path(self.conf.CONFIG_DIR) / \
        #            f"{self.parent_service_id}" / "apps" \
        #            / f"{self.service_id}.json"
        # if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
        #    shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))


def register_wsgi_app(
    context,
    app_class,
    service_id,
    client_conf,
    db,
    ):
    def app_factory():
        kwargs = {
            "conf": client_conf,
            "db": db,
            "service_id": service_id,
        }
        return app_class(**kwargs)
    register_factory(context, app_class, app_factory)


# def apps_all(conf: ClientConfig):
#    with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
#        apps_db = db.table('apps')
#        return apps_db.all()
