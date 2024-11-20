import subprocess

import pydantic

from pikesquares import conf, is_port_open
from pikesquares.services import register_factory


class ProcessComposeUnavailableException(Exception):
    pass


class ProcessCompose(pydantic.BaseModel):
    api_port: int
    client_conf: conf.ClientConfig
    # db: TinyDB

    # model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)

    def __repr__(self) -> str:
        return f"process-compose 127.0.0.1:{self.api_port}"

    def __str__(self) -> str:
        return self.__repr__()

    def ping(self) -> None:
        if not is_port_open(self.api_port):
            raise ProcessComposeUnavailableException()

    def up(self) -> None:

        try:
            compl = subprocess.run(
                args=[
                  str(self.client_conf.PROCESS_COMPOSE_BIN),
                  "up",
                  "--config",
                  str(self.client_conf.DATA_DIR / "process-compose.yml"),
                  "--detached",
                  "--port",
                  str(self.api_port),
                ],
                cwd=str(self.client_conf.DATA_DIR),
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as cperr:
            print(f"failed to launch process-compose: {cperr.stderr.decode()}")
            return

        if compl.returncode != 0:
            print("unable to launch process-compose")
        else:
            print("launched process-compose")

        print(compl.stderr.decode())
        print(compl.stdout.decode())

    def attach(self) -> None:
        try:
            compl = subprocess.run(
                args=[
                  str(self.client_conf.PROCESS_COMPOSE_BIN),
                  "attach",
                  "--port",
                  str(self.api_port),
                ],
                cwd=str(self.client_conf.DATA_DIR),
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as cperr:
            print(f"failed to attach to server: {cperr.stderr.decode()}")
            return

        if compl.returncode != 0:
            print("unable to attach server")

        print(compl.stderr.decode())
        print(compl.stdout.decode())


def register_process_compose(context, client_conf, api_port: int = 9555):

    def process_compose_factory():
        return ProcessCompose(
            api_port=api_port,
            client_conf=client_conf,
            # db=get(context, TinyDB),
        )
    register_factory(
        context,
        ProcessCompose,
        process_compose_factory,
        ping=lambda svc: svc.ping(),
    )
