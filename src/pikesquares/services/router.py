import json
from pathlib import Path

#import zmq
from tinydb import TinyDB, Query

from ..presets.routers import HttpsRouterSection
from ..conf import ClientConfig
from . import (
    Handler, 
    HandlerFactory, 
    HttpsRouter,
)


@HandlerFactory.register('Https-Router')
class HttpsRouterService(Handler):
    is_internal = False
    is_enabled = True


    config_json = {}
    #zmq_socket = zmq.Socket(zmq.Context(), zmq.PUSH)

    def prepare_service_config(
            self, 
            address: str, 
            ) -> None:


        def https_router_provision_cert():
            pass

        https_router_provision_cert()
    
        section = HttpsRouterSection(self.svc_model, address)
        self.config_json = json.loads(
                section.as_configuration().format(formatter="json"))
        self.config_json["uwsgi"]["show-config"] = True
        self.config_json["uwsgi"]["strict"] = False
        # print(f"{wsgi_app_opts=}")
        # print(f"wsgi app {self.config_json=}")
        #empjs["uwsgi"]["plugin"] = "emperor_zeromq"
        print(self.config_json)

        #self.svc_model.service_config.write_text(json.dumps(self.config_json))

        with TinyDB(self.svc_model.device_db_path) as db:
            print("Updating routers db.")
            routers_db = db.table('routers')
            routers_db.upsert(
                {
                    'service_type': self.handler_name, 
                    'service_id': self.svc_model.service_id,
                    'address': address,
                    'service_config': self.config_json,
                },
                Query().service_id == self.svc_model.service_id,
            )
            print("Done updating routers db.")


    def connect(self):
        pass
        #print(f"Connecting to zmq emperor  {self.client_config.EMPEROR_ZMQ_ADDRESS}")
        #self.zmq_socket.connect(f"tcp://{self.client_config.EMPEROR_ZMQ_ADDRESS}")

    def start(self):
        #if all([
        #    self.service_config, 
        #    isinstance(self.service_config, Path), 
        #    self.service_config.exists()]):
        #    msg = json.dumps(self.config_json).encode()
            #self.service_config.read_text()

        #    print("sending https router config to zmq")
        #    self.zmq_socket.send_multipart(
        #        [
        #            b"touch", 
        #            self.config_name.encode(), 
        #            msg,
        #        ]
        #    )
        #    print("sent https router config to zmq")
        #else:
        #    print(f"DID NOT SEND https router config to zmq {str(self.service_config.resolve())}")

        self.svc_model.service_config.parent.mkdir(parents=True, exist_ok=True)
        self.svc_model.service_config.write_text(json.dumps(self.config_json))

    def stop(self):
        pass
        #self.zmq_socket.send_multipart([
        #    b"destroy",
        #    self.config_name.encode(),
        #])
    """
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

        Path(self.service_config).parent.mkdir(parents=True, exist_ok=True)
        self.service_config.write_text(json.dumps(self.config_json))

    def stop(self):
        if self.service_config is None:
            self.service_config = Path(self.client_config.CONFIG_DIR) /  "routers" / f"{self.service_id}.json"
        if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
            shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))
    """

    
def https_router_up(
        client_config: ClientConfig, 
        service_id:str, 
        address: str,
        ) -> None:

    svc_model = HttpsRouter(
        service_id=service_id,
        client_config=client_config,
    )

    https_router = HandlerFactory.make_handler("Https-Router")(svc_model)
    https_router.prepare_service_config(address)
    https_router.connect()
    https_router.start()

def https_routers_all(client_config: ClientConfig):
    with TinyDB(f"{Path(client_config.DATA_DIR) / 'device-db.json'}") as db:
        routers_db = db.table('routers')
        return routers_db.all()


