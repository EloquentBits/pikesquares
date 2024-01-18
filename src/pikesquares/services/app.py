import json
from pathlib import Path
import shutil

#import zmq
from tinydb import TinyDB, Query

from .. import get_service_status
from . import Handler, HandlerFactory
from .project import project_up
from ..presets.wsgi_app import WsgiAppSection
from ..conf import ClientConfig

from .data import VirtualHost


@HandlerFactory.register('WSGI-App')
class WsgiAppService(Handler):

        #for k in config.keys():
        #    if k.endswith("_DIR"):
        #        dir = Path(config[k])
        #        if dir and not dir.exists():
        #            dir.mkdir(parents=True, exist_ok=True)

        #emperor_wrapper = Path(config.get("VENV_DIR", "")) / "bin/uwsgi"
        #if not emperor_wrapper.exists():
            #parser.exit(1, message=f"unable to locate VConf binary wrapper @ {emperor_wrapper}.")
        #    return

    is_internal = False
    is_enabled = True

    name: str
    service_id: str
    project_id: str
    pyvenv_dir: str
    wsgi_file: str = ""
    wsgi_module: str = ""
    virtual_hosts: list[VirtualHost] = []

    #zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    config_json = None

    def prepare_service_config(
        self,
        name: str,
        project_id: str,
        service_id: str,
        **app_options
    ):
        self.name = name
        self.service_id = service_id
        self.project_id = project_id
        self.service_config = Path(self.client_config.CONFIG_DIR) / \
                f"{self.project_id}" / "apps" \
                / f"{self.name}.json"

        self.prepare_virtual_hosts()

        with TinyDB(self.device_db_path) as db:
            routers_db = db.table('routers')
            router = routers_db.get(Query().service_id == app_options.get('router_id'))
            subscription_server_address = router.get('service_config')['uwsgi']['http-subscription-server']

            section = WsgiAppSection(
                self.client_config,
                self.name,
                self.service_id,
                self.project_id,
                subscription_server_address,
                virtual_hosts=self.virtual_hosts,
                **app_options
            ).as_configuration().format(formatter="json")
            self.config_json = json.loads(section)

            self.config_json["uwsgi"]["show-config"] = True
            self.config_json["uwsgi"]["strict"] = False

            print(self.config_json)
            self.service_config.write_text(json.dumps(self.config_json))

            print("Updating aps db.")
            apps_db = db.table('apps')
            apps_db.upsert({
                    'service_type': self.handler_name, 
                    'name': self.name, 
                    'service_id': self.service_id,
                    'project_id': self.project_id,
                    'service_config': self.config_json,
                },
                Query().service_id == self.service_id,
            )
            print("Done updating apps db.")
    

    @property
    def default_options(self):
        """
        Mapping of option key and its defaults
        """
        return {
            "root_dir": "",
            "pyvenv_dir": "{root_dir}/.venv",
            "wsgi_file": "{root_dir}/wsgi.py",
            "wsgi_module": "application",
            "python_version": "3.11"
        }

    def prepare_virtual_hosts(self, include_proj_in_url: bool=False):
        # if not self.virtual_hosts:
        self.setup_address()
        server_names = [
            # f"{self.service_id}-{self.project_id}-vconf.local",
            # f"{self.name}-{self.project_name}-vconf.local",
             f"{self.name}.{self.project_name}.pikesquares.dev" \
                if include_proj_in_url else f"{self.name}.pikesquares.dev",
        ]
        self.virtual_hosts = [
            VirtualHost(
                address=self.address,
                certificate_path=self.client_config.CERT,
                certificate_key=self.client_config.CERT_KEY,
                server_names=[sn for sn in server_names if "--" not in sn]
            )
        ]

    def connect(self):
        pass
        #emperor_zmq_opt = uwsgi.opt.get('emperor', b'').decode()
        #zmq_port = emperor_zmq_opt.split(":")[-1]
        #zmq_port = "5500"
        #self.zmq_socket.connect(f'tcp://127.0.0.1:{zmq_port}')

    def start(self):
        if not self.is_started() and str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(
                str(self.service_config),
                self.service_config.removesuffix(".stopped")
            )

        if not get_service_status(self.project_id, self.client_config) == "running":
            project = get_project(self.client_config, self.project_id)
            if project:
                project_up(self.client_config, project.get('name'), self.project_id)

        
        self.service_config.parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

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

    def stop(self):
        if self.service_config is None:
            self.service_config = Path(self.client_config.CONFIG_DIR) / \
                    f"{self.parent_service_id}" / "apps" \
                    / f"{self.service_id}.json"
        if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))


def wsgi_app_up(
        client_config: ClientConfig, 
        name: str, 
        project_id: str,
        service_id: str,
        **app_options
    ) -> None:

    app = HandlerFactory.make_handler("WSGI-App")(
        service_id=service_id, 
        client_config=client_config,
    )
    app.prepare_service_config(
        name,
        project_id,
        service_id,
        **app_options,
    )
    app.connect()
    app.start()

def apps_all(client_config: ClientConfig):
    with TinyDB(f"{Path(client_config.DATA_DIR) / 'device-db.json'}") as db:
        apps_db = db.table('apps')
        return apps_db.all()

