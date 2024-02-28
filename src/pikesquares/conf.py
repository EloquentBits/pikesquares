from pydantic_settings import (
    BaseSettings, 
    SettingsConfigDict,
)

class ClientConfig(BaseSettings):

    model_config = SettingsConfigDict()

    RUN_AS_UID: int
    RUN_AS_GID: int
    APP_NAME: str = "pikesquares"

    DEBUG: bool = False
    DAEMONIZE: bool = False
    DATA_DIR: str
    RUN_DIR: str
    LOG_DIR: str
    CONFIG_DIR: str
    PLUGINS_DIR: str
    VIRTUAL_ENV: str
    EMPEROR_ZMQ_ADDRESS: str
    PKI_DIR: str
    version: str

