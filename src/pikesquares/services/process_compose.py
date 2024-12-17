import os
import subprocess
from pathlib import Path

import pydantic
import requests

from pikesquares import conf, is_port_open
from pikesquares.services.base import ServiceUnavailableError
from pikesquares.services import register_factory
from pikesquares.cli.console import console


class PCAPIUnavailableError(ServiceUnavailableError):
    pass


class PCDeviceUnavailableError(ServiceUnavailableError):
    pass


class ProcessComposeProcessStats(pydantic.BaseModel):

    IsRunning: bool
    age: int
    cpu: float
    exit_code: int
    is_elevated: bool
    is_ready: str
    mem: int
    name: str
    namespace: str
    password_provided: bool
    pid: int
    restarts: int
    status: str
    system_time: str


class ProcessCompose(pydantic.BaseModel):
    api_port: int
    # uwsgi_bin: Path
    client_conf: conf.ClientConfig
    # db: TinyDB

    # model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)

    def __repr__(self) -> str:
        return f"process-compose ... -p 127.0.0.1:{self.api_port}"

    def __str__(self) -> str:
        return self.__repr__()

    def ping(self) -> None:
        if not is_port_open(self.api_port):
            raise PCAPIUnavailableError()

    def ping_api(self) -> bool:
        if not is_port_open(self.api_port):
            raise PCAPIUnavailableError()

        try:
            url = f"http://127.0.0.1:{self.api_port}/processes"
            response = requests.get(url, timeout=5)
            print(f"ping process-compose api: {response.status_code}")
            try:
                print(response.json())
            except ValueError:
                print("not json. skipping")
                return False
            js = response.json()
            try:
                device_process = \
                        next(filter(lambda p: p.get("name") == "Device", js.get("data", {})))
                process_stats = ProcessComposeProcessStats(**device_process)
                if process_stats.IsRunning and process_stats.status == "Running":
                    return True
            except (IndexError, StopIteration):
                pass
        except requests.ConnectionError:
            console.warning("Connection Error to process-compose API")
        except requests.Timeout:
            console.warning("Request to process-compose API timed out")

        raise PCDeviceUnavailableError()


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
        cmd_env = {
            "SCIE_BOOT": "process-compose-up",
            "COMPOSE_SHELL": "/bin/zsh", # compose_shell,
            "PIKESQUARES_VERSION": self.client_conf.version,
            #"PIKESQUARES_UWSGI_BIN": str(self.client_conf.UWSGI_BIN),
        }
        try:
            compl = subprocess.run(
                server_bin,
                env=cmd_env,
                shell=True,
                cwd=datadir,
                capture_output=True,
                check=True,
                user=self.client_conf.SERVER_RUN_AS_UID,
            )
        except subprocess.CalledProcessError as cperr:
            console.error(f"failed to launch process-compose: {cperr.stderr.decode()}")
            return

        # if compl.returncode != 0:
        #    print("unable to launch process-compose")
        if compl.stderr:
            console.info(compl.stderr.decode())
        if compl.stdout:
            console.info(compl.stdout.decode())

    def down(self) -> None:
        datadir = self.client_conf.DATA_DIR
        server_bin = os.environ.get("SCIE_ARGV0")
        # if server_bin and Path(server_bin).exists():
        compose_shell = os.environ.get("SHELL")
        console.info(f"{compose_shell=}")
        cmd_env = {
            "SCIE_BOOT": "process-compose-down",
            "COMPOSE_SHELL": compose_shell,
            "PIKESQUARES_VERSION": self.client_conf.version,
        }
        console.info(cmd_env)
        console.info(f"{server_bin=}")
        try:
            compl = subprocess.run(
                server_bin,
                env=cmd_env,
                shell=True,
                cwd=datadir,
                capture_output=True,
                check=True,
                user=self.client_conf.SERVER_RUN_AS_UID,
            )
        except subprocess.CalledProcessError as cperr:
            console.warning(f"failed to shut down process-compose: {cperr.stderr.decode()}")
            return

        # if compl.returncode != 0:
        #    print("unable to shut down process-compose")
        print(compl.args)
        print(compl)

        if compl.stderr:
            console.info(compl.stderr.decode())
        if compl.stdout:
            console.info(compl.stdout.decode())

    def attach(self) -> None:
        datadir = self.client_conf.DATA_DIR
        server_bin = os.environ.get("SCIE_ARGV0")
        # if server_bin and Path(server_bin).exists():
        compose_shell = "sh" #os.environ.get("SHELL")
        #cmd = Path(server_bin) / ""
        try:
            compl = subprocess.run(
                f"{server_bin}",
                env={
                    "SCIE_BOOT": "process-compose-attach",
                    "COMPOSE_SHELL": compose_shell,
                    "PIKESQUARES_VERSION": self.client_conf.version,
                    "XDG_CONFIG_HOME": "/home/pk/.config",
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
        pc_config = str(datadir / "process-compose.yml")

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


def register_process_compose(
        context,
        client_conf: conf.ClientConfig,
        # uwsgi_bin: Path,
        api_port: int = 9555,
    ):

    def process_compose_factory():
        return ProcessCompose(
            api_port=api_port,
            client_conf=client_conf,
            # uwsgi_bin=uwsgi_bin,
            # db=get(context, TinyDB),
        )
    register_factory(
        context,
        ProcessCompose,
        process_compose_factory,
        ping=lambda svc: svc.ping(),
    )
