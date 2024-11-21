import os
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

    def list_processes(self):
        # process-compose list --port 9555 --output json
        # [
        #        {
        #                "name": "Device",
        #                "namespace": "default",
        #                "status": "Running",
        #                "system_time": "20m",
        #                "age": 1178211038484,
        #                "is_ready": "-",
        #                "restarts": 0,
        #                "exit_code": 0,
        #                "pid": 3968629,
        #                "is_elevated": false,
        #                "password_provided": false,
        #                "mem": 1708032,
        #                "cpu": 0,
        #                "IsRunning": true
        #        }
        # ]
        pass

    def up(self) -> None:
        datadir = self.client_conf.DATA_DIR
        server_bin = os.environ.get("SCIE_ARGV0")
        # if server_bin and Path(server_bin).exists():
        compose_shell = os.environ.get("SHELL")
        try:
            compl = subprocess.run(
                server_bin,
                env={
                    "SCIE_BOOT": "process-compose-up",
                    "COMPOSE_SHELL": compose_shell,
                    "PIKESQUARES_VERSION": self.client_conf.version,
                },
                shell=True,
                cwd=datadir,
                capture_output=True,
                check=True,
                user=self.client_conf.SERVER_RUN_AS_UID,
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
        datadir = self.client_conf.DATA_DIR
        server_bin = os.environ.get("SCIE_ARGV0")
        # if server_bin and Path(server_bin).exists():
        compose_shell = os.environ.get("SHELL")
        try:
            compl = subprocess.run(
                server_bin,
                env={
                    "SCIE_BOOT": "process-compose-attach",
                    "COMPOSE_SHELL": compose_shell,
                    "PIKESQUARES_VERSION": self.client_conf.version,
                },
                shell=True,
                cwd=datadir,
                capture_output=True,
                check=True,
                user=self.client_conf.SERVER_RUN_AS_UID,
            )
        except subprocess.CalledProcessError as cperr:
            print(f"failed to attach to process-compose: {cperr.stderr.decode()}")
            return

        if compl.returncode != 0:
            print("unable to attach to process-compose")
        else:
            print("attached to process-compose")

        print(compl.stderr.decode())
        print(compl.stdout.decode())



    def up_direct(self) -> None:
        datadir = self.client_conf.DATA_DIR
        logdir = self.client_conf.LOG_DIR
        server_bin = os.environ.get("SCIE_ARGV0")
        # if server_bin and Path(server_bin).exists():
        print(f"{server_bin=}")
        # args = [
        #  str(self.client_conf.PROCESS_COMPOSE_BIN),
        #  "up",
        #  "--config",
        #  str(datadir / "process-compose.yml"),
        #  "--detached",
        #  "--port",
        #  str(self.api_port),
        # ],
        pc_config = str(datadir / 'process-compose.yml')

        args_str = f"{str(self.client_conf.PROCESS_COMPOSE_BIN)} up --config {pc_config} --detached --port {str(self.api_port)}"

        print(f"{args_str=}")

        try:
            compl = subprocess.run(
                args_str,
                env={
                    "DATA_DIR": str(datadir),
                    "LOG_DIR": str(logdir),
                    "SERVER_EXE": server_bin,
                    "COMPOSE_SHELL": "/usr/bin/sh",
                    "PIKESQUARES_VERSION": self.client_conf.version,

                },
                shell=True,
                cwd=datadir,
                capture_output=True,
                check=True,
                user=self.client_conf.SERVER_RUN_AS_UID,
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

    def attach_direct(self) -> None:
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
