import json
import os
import pwd
import grp
from pathlib import Path
from functools import cached_property
from typing import (
    # Any,
    # Dict,
    # Tuple,
    # Type,
    Optional,
    Annotated,
)

# from questionary import Style as QuestionaryStyle

import pydantic
from pydantic_settings import (
    BaseSettings,
    # PydanticBaseSettingsSource,
    SettingsConfigDict,
)
# from pydantic.fields import FieldInfo
import structlog

from pikesquares.services import register_factory
from pikesquares.cli.console import console

logger = structlog.get_logger()


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

"""

      "RUN_AS_UID": 1000,
      "RUN_AS_GID": 1000,
      "SERVER_RUN_AS_UID": 1000,
      "SERVER_RUN_AS_GID": 1000,
      "DATA_DIR": "/home/pk/.local/share/pikesquares",
      "RUN_DIR": "/run/user/1000/pikesquares",
      "LOG_DIR": "/home/pk/.local/state/pikesquares/log",
      "CONFIG_DIR": "/home/pk/.config/pikesquares",
      "PLUGINS_DIR": "/home/pk/.local/share/pikesquares/plugins",
      "PKI_DIR": "/home/pk/.local/share/pikesquares/pki",
      "EASYRSA_DIR": "/home/pk/.cache/nce/ec0fdca46c07afef341e0e0eeb2bf0cfe74a11322b77163e5d764d28cb4eec89/easyrsa",
      "EASYRSA_BIN": "/home/pk/.cache/nce/ec0fdca46c07afef341e0e0eeb2bf0cfe74a11322b77163e5d764d28cb4eec89/easyrsa/EasyRSA-3.2.1/easyrsa",
      "SENTRY_DSN": "123",
      "version": "0.0.38.dev0",
      "UWSGI_BIN": "/home/pk/.cache/nce/fafc9b47294ed168f7c6d827aa0a4a6b2fccb523c47301a08d64ba14e283109a/uwsgi/uwsgi",
      "VIRTUAL_ENV": "/home/pk/.cache/nce/ccdb0dbe69a24abb4f4ad5bc8bf57dd9fb683143ed6c6c4fbcd8ec8b0a15d651/bindings/venvs/0.0.38.dev0"

"""


class AppConfigError(Exception):
    pass


# directory layout
# root
#       data_dir = /var/lib/pikesquares
#       run_dir = /var/run/pikesquares
#       conf_dir = /etc/pikesquares
#       log_dir = /var/log/pikesquares


class SysDir(pydantic.BaseModel):

    # path_to_dir: Path
    path_to_dir: pydantic.DirectoryPath = pydantic.Field()
    env_var: str
    dir_mode: int = 0o775
    owner_username: str = "root"
    owner_groupname: str = "pikesquares"


def make_system_dir(
        newdir: Path | str,
        owner_username: str = "root",
        owner_groupname: str = "pikesquares",
        dir_mode: int = 0o775,
    ) -> Path:
    if isinstance(newdir, str):
        newdir = Path(newdir)

    if newdir.exists():
        return newdir

    logger.info(f"make_system_dir: mkdir {str(newdir)}")
    newdir.mkdir(mode=dir_mode, parents=True, exist_ok=True)

    logger.info(f"make_system_dir: chown {owner_username}:{owner_groupname}")
    try:
        owner_uid = pwd.getpwnam(owner_username)[2]
    except KeyError:
        raise AppConfigError(f"unable locate user: {owner_username}") from None

    try:
        owner_gid = grp.getgrnam(owner_groupname)[2]
    except KeyError:
        raise AppConfigError(f"unable locate group: {owner_groupname}") from None

    os.chown(
        newdir,
        owner_uid,
        owner_gid,
    )

    # pwd.getpwnam(owner_uid).pw_uid,
    # pwd.getpwnam(owner_gid).pw_gid


def ensure_sysdir(dir_path, varname):
    dir_path = dir_path or os.environ.get(f"PIKESQUARES_{varname}")
    if not dir_path:
        dir_path = make_system_dir(Path("/var/lib/pikesquares"))
        logger.info(f"new dir with default path: {str(dir_path)}")
        return dir_path
    elif not Path(dir_path).exists():
        dir_path = make_system_dir(Path(dir_path))
        logger.info(f"new dir with a user provided path: {str(dir_path)}")
        return dir_path


def get_lift_file_section(lift_file: Path, lift_file_key: str):

    # {
    #  "name": "easyrsa",
    #  "size": 79917,
    #  "hash": "ec0fdca46c07afef341e0e0eeb2bf0cfe74a11322b77163e5d764d28cb4eec89",
    #  "type": "tar.gz",
    #  "source": "fetch"
    # },

    # os_name = "macos" if os.uname().sysname.lower() == "darwin" else "linux"
    # platform = f"{os_name}-{os.uname().machine}"

    if not all([lift_file, Path(lift_file).exists()]):
        console.warning("unable to locate scie lift file")
        raise AppConfigError("unable to locate scie lift file") from None

    with open(lift_file, encoding="utf-8") as lf:
        lift_json = json.loads(lf.read())
        lift_files = lift_json["scie"]["lift"]["files"]
        return next(filter(lambda x: x.get("key") == lift_file_key, lift_files))


class AppConfig(BaseSettings):

    model_config = SettingsConfigDict(
        env_prefix="PIKESQUARES_",
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = pydantic.Field(default="pikesquares")
    VERSION: str = pydantic.Field()
    server_run_as_uid: str = pydantic.Field(default="root")
    server_run_as_gid: str = pydantic.Field(default="root")

    # DEBUG: bool = False
    data_dir: pydantic.DirectoryPath = pydantic.Field(
            default=Path("/var/lib/pikesquares"),
            alias="PIKESQUARES_DATA_DIR"
    )

    log_dir: pydantic.DirectoryPath = pydantic.Field(
            default=Path("/var/log/pikesquares"),
            alias="PIKESQUARES_LOG_DIR"
    )

    config_dir: pydantic.DirectoryPath = pydantic.Field(
            default=Path("/etc/pikesquares"),
            alias="PIKESQUARES_CONFIG_DIR"
    )

    run_dir: pydantic.DirectoryPath = pydantic.Field(
            default=Path("/var/run/pikesquares"),
            alias="PIKESQUARES_RUN_DIR"
    )
    UWSGI_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None
    PYTHON_VIRTUAL_ENV: Optional[Annotated[pydantic.DirectoryPath, pydantic.Field()]]

    SCIE_BASE: Optional[Annotated[pydantic.DirectoryPath, pydantic.Field()]] = None
    SCIE_BINDINGS: Optional[Annotated[pydantic.DirectoryPath, pydantic.Field()]] = None
    SCIE_LIFT_FILE: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None

    EASYRSA_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None
    DNSMASQ_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None
    CADDY_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None
    UV_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None
    PROCESS_COMPOSE_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None
    PROCESS_COMPOSE_CONFIG: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None

    # CADDY_DIR: Optional[str] = None
    # CLI_STYLE: QuestionaryStyle

    sentry_enabled: bool = False
    sentry_dsn: str | None = None
    daemonize: bool = False

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        path_to_db = self.data_dir / "pikesquares.db"
        return f"sqlite+aiosqlite:///{str(path_to_db)}"

    @pydantic.computed_field
    @cached_property
    def default_app_run_as_uid(self) -> int:
        return pwd.getpwnam("pikesquares").pw_uid

    @pydantic.computed_field
    @cached_property
    def default_app_run_as_gid(self) -> int:
        return pwd.getpwnam("pikesquares").pw_gid

    @pydantic.computed_field
    @cached_property
    def pki_dir(self) -> Path:
        return make_system_dir(self.data_dir / "pki")

    @pydantic.computed_field
    @cached_property
    def uv_cache_dir(self) -> Path:
        return make_system_dir(self.data_dir / "uv-cache")

    @pydantic.computed_field
    @cached_property
    def plugins_dir(self) -> Path:
        return make_system_dir(self.data_dir / "plugins")

    @pydantic.computed_field
    @cached_property
    def lift_file(self) -> Path | None:
        if self.SCIE_LIFT_FILE:
            return self.SCIE_LIFT_FILE
        elif self.SCIE_BASE:
            return self.SCIE_BASE / "lift.json"
    """
    @pydantic.computed_field
    @property
    def easyrsa_bin(self) -> Path:
        easyrsa_relative_path = "easyrsa/EasyRSA-3.2.1/easyrsa"
        if self.EASYRSA_DIR:
            bin_path = self.EASYRSA_DIR / easyrsa_relative_path
            if not bin_path.exists():
                raise AppConfigError(f"unable to locate the EasyRSA script at {bin_path}") from None
        else:
            if not self.lift_file:
                raise AppConfigError("unable to locate scie lift file") from None

            file_section = get_lift_file_section(self.lift_file, "easyrsa")
            if self.SCIE_BASE and not self.SCIE_BASE.exists():
                raise AppConfigError("unable to locate SCIE_BASE directory") from None

            bin_path = self.SCIE_BASE / file_section.get("hash") / easyrsa_relative_path
            print(bin_path)
            if not bin_path.exists():
                raise AppConfigError(f"unable to locate the EasyRSA script at {bin_path}") from None
        return bin_path

    """

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


def register_app_conf(
        context: dict,
        override_settings: dict,
    ):
    def conf_factory() -> AppConfig:
        return AppConfig(**override_settings)

    register_factory(context, AppConfig, conf_factory)
