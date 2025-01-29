import os
import subprocess
from pathlib import Path

import pydantic
import requests

from pikesquares import is_port_open
from pikesquares.conf import AppConfig
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
    conf: AppConfig
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
            # print(f"ping process-compose api: {response.status_code}")
            try:
                js = response.json()
            except ValueError:
                console.warning(f"process-compose proceses API did not return valid json. {response=}")
                return False
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
        #  str(self.conf.PROCESS_COMPOSE_BIN),
        #  "up",
        #  "--config",
        #  str(datadir / "process-compose.yml"),
        #  "--detached",
        #  "--port",
        #  str(self.api_port),
        # ],

        pc_config = self.conf.PROCESS_COMPOSE_CONFIG
        pc_bin = self.conf.PROCESS_COMPOSE_DIR / "process-compose"

        cmd_env = {
            "COMPOSE_SHELL": os.environ.get("SHELL"),
            "PIKESQUARES_VERSION": self.conf.VERSION,
            "PIKESQUARES_UWSGI_BIN": str(self.conf.uwsgi_bin),
            "PIKESQUARES_VIRTUAL_ENV": str(self.conf.VIRTUAL_ENV),
            "PIKESQUARES_CADDY_BIN": str(self.conf.CADDY_BIN),
            "PIKESQUARES_DNSMASQ_BIN": str(self.conf.DNSMASQ_BIN),
            "PIKESQUARES_SCIE_BASE": str(self.conf.SCIE_BASE),
            "PIKESQUARES_SCIE_LIFT_FILE": str(self.conf.SCIE_LIFT_FILE),
            "PIKESQUARES_EASYRSA_DIR": str(self.conf.EASYRSA_DIR),
            "PIKESQUARES_PROCESS_COMPOSE_DIR": str(self.conf.PROCESS_COMPOSE_DIR),
        }
        cmd_args = [
            str(pc_bin),
            "up",
            "--config",
            str(pc_config),
            "--log-file",
            str(self.conf.log_dir / "process-compose.log"),
            "--detached",
            "--hide-disabled",
            "--port",
            str(self.conf.PC_PORT_NUM),
        ]
        print("calling process-compose up")
        print(cmd_env)
        print(cmd_args)

        try:
            popen = subprocess.Popen(
                cmd_args,
                env=cmd_env,
                cwd=self.conf.data_dir,
                stdout=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True,
                user=self.conf.server_run_as_uid,
                group=self.conf.server_run_as_gid,
            )
            for line in iter(popen.stdout.readline, ""):
                print(line, end="")

            popen.stdout.close()
            popen.wait()

        except subprocess.CalledProcessError as cperr:
            console.error(f"failed to launch process-compose: {cperr.stderr.decode()}")
            print(f"failed to launch process-compose: {cperr.stderr.decode()}")
            return
        """

        args_str = f"{str(self.conf.PROCESS_COMPOSE_BIN)} up --config {pc_config} --detached --port {str(self.api_port)}"

        print(f"{args_str=}")

        try:
            compl = subprocess.run(
                args_str,
                env={
                    "DATA_DIR": str(self.conf.data_dir),
                    "LOG_DIR": str(self.conf.log_dir),
                    "SERVER_EXE": os.environ.get("SCIE_ARGV0"),
                    "COMPOSE_SHELL": "/usr/bin/sh",
                    "PIKESQUARES_VERSION": self.conf.version,

                },
                shell=True,
                cwd=self.conf.data_dir,
                capture_output=True,
                check=True,
                user=self.conf.server_run_as_uid,
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
        """

    def up_scie(self) -> None:
        server_bin = os.environ.get("SCIE_ARGV0")
        # if server_bin and Path(server_bin).exists():
        console.info(f"{os.environ.get("SHELL")=}")
        console.info(f"{self.conf.uwsgi_bin=}")
        cmd_env = {
            "SCIE_BOOT": "process-compose-up",
            "COMPOSE_SHELL": os.environ.get("SHELL"),
            "PIKESQUARES_VERSION": self.conf.VERSION,
            "PIKESQUARES_UWSGI_BIN": str(self.conf.uwsgi_bin),
        }
        try:
            # compl = subprocess.run(
            #    server_bin,
            #    env=cmd_env,
            #    shell=True,
            #    cwd=datadir,
            #    capture_output=True,
            #    check=True,
            #    user=self.conf.server_run_as_uid,
            # )

            popen = subprocess.Popen(
                server_bin,
                env=cmd_env,
                cwd=self.conf.data_dir,
                stdout=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True,
                user=0,
                group=0,
            )
            for line in iter(popen.stdout.readline, ""):
                print(line, end="")

            popen.stdout.close()
            popen.wait()

        except subprocess.CalledProcessError as cperr:
            console.error(f"failed to launch process-compose: {cperr.stderr.decode()}")
            return

        # if compl.returncode != 0:
        #    print("unable to launch process-compose")
        # if compl.stderr:
        #    console.info(compl.stderr.decode())
        # if compl.stdout:
        #    console.info(compl.stdout.decode())


    def down(self) -> None:
        datadir = self.conf.data_dir
        server_bin = os.environ.get("SCIE_ARGV0")
        # if server_bin and Path(server_bin).exists():
        compose_shell = os.environ.get("SHELL")
        console.info(f"{compose_shell=}")
        cmd_env = {
            "SCIE_BOOT": "process-compose-down",
            "COMPOSE_SHELL": compose_shell,
            "PIKESQUARES_VERSION": self.conf.VERSION,
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
                user=self.conf.server_run_as_uid,
            )
        except subprocess.CalledProcessError as cperr:
            console.warning(f"failed to shut down process-compose: {cperr.stderr.decode()}")
            return

        # if compl.returncode != 0:
        #    print("unable to shut down process-compose")
        print(compl.args)
        print(compl)

        if compl.stderr:
            console.warning(compl.stderr.decode())
        if compl.stdout:
            console.info(compl.stdout.decode())

    def up_direct(self) -> None:
        #  str(self.conf.PROCESS_COMPOSE_BIN),
        #  "up",
        #  "--config",
        #  str(datadir / "process-compose.yml"),
        #  "--detached",
        #  "--port",
        #  str(self.api_port),
        # ],
        pc_config = str(self.conf.data_dir / "process-compose.yml")

        args_str = f"{str(self.conf.PROCESS_COMPOSE_BIN)} up --config {pc_config} --detached --port {str(self.api_port)}"

        print(f"{args_str=}")

        try:
            compl = subprocess.run(
                args_str,
                env={
                    "DATA_DIR": str(self.conf.data_dir),
                    "LOG_DIR": str(self.conf.log_dir),
                    "SERVER_EXE": os.environ.get("SCIE_ARGV0"),
                    "COMPOSE_SHELL": "/usr/bin/sh",
                    "PIKESQUARES_VERSION": self.conf.VERSION,

                },
                shell=True,
                cwd=self.conf.data_dir,
                capture_output=True,
                check=True,
                user=self.conf.server_run_as_uid,
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
                  # str(self.conf.PROCESS_COMPOSE_BIN),
                  str(Path(os.environ.get("PIKESQUARES_PROCESS_COMPOSE_DIR")) / "process-compose"),
                  "attach",
                  "--port",
                  str(self.api_port),
                ],
                cwd=str(self.conf.data_dir),
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
        conf: AppConfig,
        # uwsgi_bin: Path,
        api_port: int = 9555,
    ):

    def process_compose_factory():
        return ProcessCompose(
            api_port=api_port,
            conf=conf,
            # uwsgi_bin=uwsgi_bin,
            # db=get(context, TinyDB),
        )
    register_factory(
        context,
        ProcessCompose,
        process_compose_factory,
        ping=lambda svc: svc.ping(),
    )
