import os
import pwd
import platform
from pathlib import Path

import pydantic
from platformdirs import (
    user_data_dir, 
    user_runtime_dir,
    user_config_dir,
    user_log_dir,
)

from pydantic_settings import (
    BaseSettings, 
    SettingsConfigDict,
)



class VirtualHost(pydantic.BaseModel):
    address: str
    certificate_path: str
    certificate_key: str
    server_names: list[str]
    protocol: str = "https"
    static_files_mapping: dict = {}

    @property
    def is_https(self):
        return all([
            self.certificate_key,
            self.certificate_path
        ])



class ClientConfig(BaseSettings):

    model_config = SettingsConfigDict(env_file='pikesquares.conf', env_file_encoding='utf-8')

    SERVER_USER: str = "pikesquares"
    APP_NAME: str = "pikesquares"
    PORT: str = "6080"
    BIND_IP: str = "127.0.0.1"
    UPDATE_CHANNEL: str = "dev"

    DEVICE_ID: str = ""
    DEVICE_OS: str = platform.system()
    SECRET_KEY: str = ""
    API_URL: str = ""

    UID: int = pwd.getpwuid(os.getuid()).pw_uid
    GID: int = pwd.getpwuid(os.getuid()).pw_gid
    CURRENT_USER: str = pwd.getpwuid(os.getuid()).pw_name
    DATA_DIR: str = str(Path(user_data_dir(APP_NAME, CURRENT_USER)).resolve())

    DEBUG: bool = False
    DAEMONIZE: bool = False
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

    #CERT: str = str((Path(SSL_DIR) / "pikesquares.dev.pem"))  # check the paths are the same in install/uninstall scripts
    #CERT_KEY: str = str((Path(SSL_DIR) / "pikesquares.dev-key.pem"))  # check the paths are the same in install/uninstall scripts

    CERT:str = "/home/pk/dev/eqb/pikesquares/tmp/_wildcard.pikesquares.dev+2.pem"
    CERT_KEY:str = "/home/pk/dev/eqb/pikesquares/tmp/_wildcard.pikesquares.dev+2-key.pem"

