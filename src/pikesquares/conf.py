import os
import pwd
from pathlib import Path

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

current_user: str = pwd.getpwuid(os.getuid()).pw_name

class ClientConfig(BaseSettings):

    model_config = SettingsConfigDict(env_file='pikesquares.conf', env_file_encoding='utf-8')

    RUN_AS_UID: int = 1000
    RUN_AS_GID: int = 1000
    APP_NAME: str = "pikesquares"

    DEBUG: bool = False
    DAEMONIZE: bool = False

    DATA_DIR: str = str(Path(user_data_dir(APP_NAME, current_user)).resolve())
    RUN_DIR: str = str(Path(user_runtime_dir(APP_NAME, current_user)).resolve())
    LOG_DIR: str = str(Path(user_log_dir(APP_NAME, current_user)).resolve())
    CONFIG_DIR: str = str(Path(user_config_dir(APP_NAME, current_user)).resolve())
    PLUGINS_DIR: str = str((Path(DATA_DIR) / "plugins").resolve())
    VENV_DIR: str = os.environ.get("VIRTUAL_ENV", "")

    EMPEROR_ZMQ_ADDRESS: str = "127.0.0.1:5250"

    PKI_DIR: str = str((Path(DATA_DIR) / "pki").resolve())  # check the paths are the same in install/uninstall scripts

