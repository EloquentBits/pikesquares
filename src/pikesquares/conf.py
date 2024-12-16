import os
import traceback
# import json
from pathlib import Path
from typing import Any, Dict, Tuple, Type, Optional

# from questionary import Style as QuestionaryStyle

from pydantic import Field
from tinydb import TinyDB, Query
import platformdirs

from pydantic_settings import (
    BaseSettings,
    # PydanticBaseSettingsSource,
    SettingsConfigDict,
)
# from pydantic.fields import FieldInfo

from pikesquares.services import register_factory

"""
class JsonConfigSettingsSource(PydanticBaseSettingsSource):
    '''
    A simple settings source class that loads variables from a JSON file
    at the project's root.

    Here we happen to choose to use the `env_file_encoding` from Config
    when reading `config.json`
    '''

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        encoding = self.config.get('env_file_encoding')
        file_content_json = json.loads(
            Path('tests/example_test_config.json').read_text(encoding)
        )
        field_value = file_content_json.get(field_name)
        return field_value, field_name, False

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        return value

    def __call__(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(
                field, field_name
            )
            field_value = self.prepare_field_value(
                field_name, field, field_value, value_is_complex
            )
            if field_value is not None:
                d[field_key] = field_value

        return d

class JsonConfigSettingsSource(InitSettingsSource, ConfigFileSourceMixin):
    '''
    A source class that loads variables from a JSON file
    '''

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        json_file: PathType | None = DEFAULT_PATH,
        json_file_encoding: str | None = None,
    ):
        self.json_file_path = json_file if json_file != DEFAULT_PATH else settings_cls.model_config.get('json_file')
        self.json_file_encoding = (
            json_file_encoding
            if json_file_encoding is not None
            else settings_cls.model_config.get('json_file_encoding')
        )
        self.json_data = self._read_files(self.json_file_path)
        super().__init__(settings_cls, self.json_data)

    def _read_file(self, file_path: Path) -> dict[str, Any]:
        with open(file_path, encoding=self.json_file_encoding) as json_file:
            return json.load(json_file)

"""


class ClientConfigError(Exception):
    pass


class ClientConfig(BaseSettings):

    model_config = SettingsConfigDict(env_prefix='PIKESQUARES_')

    version: str
    RUN_AS_UID: int = Field(gt=0)
    RUN_AS_GID: int = Field(gt=0)
    SERVER_RUN_AS_UID: int = Field(gt=0)
    SERVER_RUN_AS_GID: int = Field(gt=0)
    APP_NAME: str = "pikesquares"

    # DEBUG: bool = False
    DATA_DIR: Path
    RUN_DIR: Path
    LOG_DIR: Path
    CONFIG_DIR: Path
    PLUGINS_DIR: Path
    VIRTUAL_ENV: Path | None = None
    EASYRSA_DIR: Path | None = None
    EASYRSA_BIN: Path | None = None
    # CADDY_DIR: Optional[str] = None
    PKI_DIR: Path | None = None
    PROCESS_COMPOSE_BIN: Path | None = None
    UWSGI_BIN: Path | None = None
    # CLI_STYLE: QuestionaryStyle
    SENTRY_ENABLED: bool = False
    SENTRY_DSN: str | None = None
    DAEMONIZE: bool = False

    # @classmethod
    # def settings_customise_sources(
    #    cls,
    #    settings_cls: Type[BaseSettings],
    #    init_settings: PydanticBaseSettingsSource,
    #    env_settings: PydanticBaseSettingsSource,
    #    #dotenv_settings: PydanticBaseSettingsSource,
    #    file_secret_settings: PydanticBaseSettingsSource,
    # ) -> Tuple[PydanticBaseSettingsSource, ...]:
    #    return (
    #        init_settings,
    #        JsonConfigSettingsSource(settings_cls),
    #        env_settings,
    #        file_secret_settings,
    #    )


def get_conf_mapping(db: TinyDB, pikesquares_version: str) -> dict:
    try:
        configs = db.table("configs").get(Query().version == pikesquares_version) or {}
        if not configs:
            current_uid = os.getuid()
            current_gid = os.getgid()
            apps_run_as_uid = None
            apps_run_as_gid = None
            configs["RUN_AS_UID"] = apps_run_as_uid or current_uid
            configs["RUN_AS_GID"] = apps_run_as_gid or current_gid

            server_run_as_uid = current_uid
            server_run_as_gid = current_gid
            new_server_run_as_uid = None
            new_server_run_as_gid = None
            configs["SERVER_RUN_AS_UID"] = new_server_run_as_uid or server_run_as_uid
            configs["SERVER_RUN_AS_GID"] = new_server_run_as_gid or server_run_as_gid

            app_name = "pikesquares"
            data_dir = platformdirs.user_data_path(app_name, ensure_exists=True)
            configs["DATA_DIR"] = str(data_dir)
            configs["RUN_DIR"] = str(platformdirs.user_runtime_path(app_name, ensure_exists=True))
            configs["LOG_DIR"] = str(platformdirs.user_log_path(app_name, ensure_exists=True))
            configs["CONFIG_DIR"] = str(platformdirs.user_config_path(app_name, ensure_exists=True))

            plugins_dir = data_dir / "plugins"
            plugins_dir.mkdir(mode=0o777, parents=True, exist_ok=True)
            configs["PLUGINS_DIR"] = str(plugins_dir)

            configs["PKI_DIR"] = str(data_dir / "pki")

            configs["EASYRSA_DIR"] = os.environ.get("PIKESQUARES_EASYRSA_DIR")
            configs["EASYRSA_BIN"] = os.environ.get("PIKESQUARES_EASYRSA_BIN")
            configs["SENTRY_DSN"] = os.environ.get("PIKESQUARES_SENTRY_DSN")
            configs["version"] = str(pikesquares_version)

            if "VIRTUAL_ENV" in os.environ:
                venv_dir = os.environ.get("VIRTUAL_ENV")
                if venv_dir and Path(venv_dir).exists() and Path(venv_dir).is_dir():
                    configs["VIRTUAL_ENV"] = venv_dir
            db.table("configs").insert(configs)
        return configs
    except Exception:
        traceback.print_exc()
        raise ClientConfigError() from None


def register_app_conf(context: dict, pikesquares_version: str, db: TinyDB):
    def conf_factory() -> ClientConfig:
        return ClientConfig(
            **get_conf_mapping(db, pikesquares_version)
        )
    register_factory(context, ClientConfig, conf_factory)
