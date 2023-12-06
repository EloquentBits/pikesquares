#import sys
import os

import pwd
import pwd
import platform
from pathlib import Path

from platformdirs import (
    user_data_dir, 
    user_runtime_dir,
    user_config_dir,
    user_log_dir,
)

from pydantic_settings import BaseSettings, SettingsConfigDict


class ClientConfig(BaseSettings):

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    SERVER_USER: str = "pikesquares"
    APP_NAME: str = "pikesquares"
    PORT: str = "6080"
    BIND_IP: str = "127.0.0.1"
    UPDATE_CHANNEL: str = "dev"

    DEVICE_ID: str = ""
    DEVICE_OS: str = platform.system()
    SECRET_KEY: str = ""
    API_URL: str = ""

    VC_DOMAIN: str = "vc.rpi.home"
    VC_PORT: str = "443"

    UID: int = pwd.getpwuid(os.getuid()).pw_uid
    GID: int = pwd.getpwuid(os.getuid()).pw_gid
    CURRENT_USER: str = pwd.getpwuid(os.getuid()).pw_name
    DATA_DIR: str = str(Path(user_data_dir(APP_NAME, CURRENT_USER)).resolve())

    DEBUG: bool = False
    DAEMONIZE: bool = False
    SSE_HOST: str = "127.0.0.1"
    SSE_PORT: str = "7999"
    SSE_HOST_HEADER: str = "vc.eloquentbits.com"
    SSE_ENDPOINT: str = "/events/apps"
    HC_PING_URL: str = ""
    ZEROMQ_MONITOR: bool = False
    DIR_MONITOR: bool = True

    RUN_DIR: str = str(Path(user_runtime_dir(APP_NAME, CURRENT_USER)).resolve())
    LOG_DIR: str = str(Path(user_log_dir(APP_NAME, CURRENT_USER)).resolve())
    CONFIG_DIR: str = str(Path(user_config_dir(APP_NAME, CURRENT_USER)).resolve())
    PLUGINS_DIR: str = str((Path(DATA_DIR) / "plugins").resolve())
    VENV_DIR: str = os.environ.get("VIRTUAL_ENV", "")

    SSL_DIR: str = str((Path(DATA_DIR) / "ssl").resolve())  # check the paths are the same in install/uninstall scripts

    EMPEROR_ZMQ_ADDRESS: str = "127.0.0.1:5250"

    HTTPS_ROUTER_SUBSCRIPTION_SERVER: str = "127.0.0.1:4667"
    HTTPS_ROUTER: str = "127.0.0.1:4443"
    HTTPS_ROUTER_STATS: str = "127.0.0.1:4657"

    CERT: str = str((Path(SSL_DIR) / "pikesquares.dev.pem"))  # check the paths are the same in install/uninstall scripts
    CERT_KEY: str = str((Path(SSL_DIR) / "pikesquares.dev-key.pem"))  # check the paths are the same in install/uninstall scripts

    #STATE_DIR: str = ""
    
    def setup_dirs(self):
       for k, v in self.__dict__.items():
           if k.endswith("_DIR"):
               mode = 511
               if k == "CONFIG_DIR":
                   mode = 666
               Path(v).mkdir(mode=mode, parents=True, exist_ok=True)

    """
    def get_var_by_name(lines, var_name):
        try:
            line = list(filter(lambda x: x.split("=")[0] == var_name, lines))[0]
            return line.split("=")[1].strip()
        except IndexError:
            return


    @anonymous_user_allowed
    def query_vconf_cloud(env_file, device_id=None, secret_key=None, api_root=None):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        url = f"{api_root}/env-bootstrap/"
        headers = {
            "X-VCONF-CLIENT-USER": f"{current_user}:{pwuid.pw_uid}:{pwuid.pw_gid}",
            "X-VCONF-CLIENT-DEVICE": f"{device_hostname}:{device_os_type}:{device_arch}",
            "X-VCONF-DATA-DIR": str(app_state["data_dir"]),
            "X-VCONF-RUN-DIR": str(app_state["run_dir"]),
            "X-VCONF-CONFIG-DIR": str(app_state["config_dir"]),
            "X-VCONF-PLUGINS-DIR": str(app_state["plugins_dir"]),
            "X-VCONF-LOG-DIR": str(app_state["log_dir"]),
        }
        if device_id and secret_key:
            url += f"?device_id={device_id}"
            headers['Authorization'] = f"Token {secret_key}"
        try:
            req = urllib.request.Request(
                url=url, 
                headers=headers,
            )
            #for dir in ["data", "run", "config", "plugins", "log"]:
            #    path = headers.get(f'X-VCONF-{dir.upper()}-DIR')
            #    print(f"{dir} dir: {path}")

            with urllib.request.urlopen(req, context=ctx) as response:
                if response.code == 403:
                    #parser.exit(1, message=f"Request Forbidden with secret_key {secret_key} @ {url}")
                    return

                body = response.read().decode()
                data = json.loads(body)
                with open(env_file, "w") as f:
                    f.truncate()
                    f.write(f"DEVICE_ID={device_id}\n")
                    f.write(f"SECRET_KEY={secret_key}\n")
                    f.write(f"API_URL={api_root}\n")
                    f.write(f"DATA_DIR={app_state.get('data_dir')}\n")
                    f.write(f"RUN_DIR={app_state.get('run_dir')}\n")
                    f.write(f"CONFIG_DIR={app_state.get('config_dir')}\n")
                    f.write(f"PLUGINS_DIR={app_state.get('plugins_dir')}\n")
                    f.write(f"LOG_DIR={app_state.get('log_dir')}\n")
                    #f.write(f"STATE_DIR={state_dir}\n")
                    for k, v in data.get("settings", {}).items():
                        f.write(f"{k}={v}\n")
                        #print(f"[bootstrap-venv] writing: {k}={v}\n")
                        #uwsgi.cache_update(k, v, 0, uwsgi_cache_name)
        except urllib.error.HTTPError as e:
        #    uwsgi.log(fh, e.code, url)
            console.error(f"Could not connect to: {url}. {str(e)}")
            #parser.exit(1, message=f"unable to connect to VConf Cloud.")
            exit(1)
        else:
            return data


    def gather_settings(env_file, device_id, secret_key, api_root):
        console.info(f"Gathering settings from {api_root}")
        if env_file.exists():
            with open(env_file, "r") as f:
                lines = f.readlines()
                if not device_id:
                    device_id = get_var_by_name(lines, "DEVICE_ID")
                if not secret_key:
                    secret_key = get_var_by_name(lines, "SECRET_KEY")
                if not api_root:
                    api_root = get_var_by_name(lines, "ADDR")

        app_state['device_id'] = device_id
        app_state['device_name'] = device_hostname
        # if not device_id:
        #     device_id = console.ask("Please enter your VConf Device ID: ", repeat=True)
        # if not secret_key:
        #     secret_key = console.ask("Please enter your VConf Secret Key: ", repeat=True)

        if not api_root:
            console.info(f"{device_id=} {secret_key=} {api_root=}")
            #parser.exit(1, message=f"could not gather all the required settings.")
            return

        query_vconf_cloud(env_file, device_id, secret_key, api_root=api_root)

    """
