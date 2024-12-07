# import json
from pathlib import Path
from typing import Any, Dict, Tuple, Type, Optional

# from questionary import Style as QuestionaryStyle

from pydantic import Field
from tinydb import TinyDB, Query

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


def get_conf_mapping(db: TinyDB, pikesquares_version: str):
    try:
        return db.\
                table("configs").\
                search(Query().version == pikesquares_version)[0]
    except IndexError:
        raise ClientConfigError(f"unable to locate config in db for v{pikesquares_version}")


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
    VIRTUAL_ENV: Path
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


def register_app_conf(context: dict, pikesquares_version: str, db: TinyDB):
    def conf_factory():
        return ClientConfig(
            **get_conf_mapping(db, pikesquares_version)
        )
    register_factory(context, ClientConfig, conf_factory)
