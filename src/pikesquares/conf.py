import warnings
import secrets
import json
import os
import pwd
import grp
from pathlib import Path
from typing import (
    Any,
    Optional,
    Annotated,
    Literal,
    Self,
)

# from questionary import Style as QuestionaryStyle
from aiopath import AsyncPath
from plumbum import local
import pydantic
from pydantic import AnyUrl, BeforeValidator
from pydantic_settings import (
    BaseSettings,
    # PydanticBaseSettingsSource,
    SettingsConfigDict,
)
import structlog

from pikesquares.services import register_factory
from pikesquares.cli.console import console
from pikesquares.adapters.database import DatabaseSessionManager

logger = structlog.get_logger()


class AppConfigError(Exception):
    pass


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)

    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="src/pikesquares/.env-app",
        # env_file="../.env-app",
        env_ignore_empty=True,
        extra="ignore",
    )


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file=".env-app",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[list[AnyUrl] | str, BeforeValidator(parse_cors)] = []

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [self.FRONTEND_HOST]

    PROJECT_NAME: str
    SENTRY_DSN: pydantic.HttpUrl | None = None
    # POSTGRES_SERVER: str
    # POSTGRES_PORT: int = 5432
    # POSTGRES_USER: str
    # POSTGRES_PASSWORD: str = ""
    # POSTGRES_DB: str = ""

    # @computed_field  # type: ignore[prop-decorator]
    # @property
    # def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
    #     return MultiHostUrl.build(
    #         scheme="postgresql+psycopg",
    #         username=self.POSTGRES_USER,
    #         password=self.POSTGRES_PASSWORD,
    #         host=self.POSTGRES_SERVER,
    #         port=self.POSTGRES_PORT,
    #         path=self.POSTGRES_DB,
    #     )

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        path_to_db = ensure_system_path(Path("/var/lib/pikesquares") / "pikesquares.db", is_dir=False)
        return f"sqlite+aiosqlite:///{path_to_db}"

        db_path: Path = ensure_system_path(self.data_dir / "pikesquares.db")
        return f"sqlite+aiosqlite:///{db_path}"

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: pydantic.EmailStr | None = None
    EMAILS_FROM_NAME: pydantic.EmailStr | None = None

    @pydantic.model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: pydantic.EmailStr = "test@example.com"
    FIRST_SUPERUSER: pydantic.EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", ' "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @pydantic.model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        # self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret("FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD)

        return self


# directory layout
# root
#       data_dir = /var/lib/pikesquares
#       run_dir = /var/run/pikesquares
#       conf_dir = /etc/pikesquares
#       log_dir = /var/log/pikesquares


def ensure_system_path(
    new_path: Path | str,
    owner_username: str = "root",
    owner_groupname: str = "pikesquares",
    owner_uid: int | None = None,
    owner_gid: int | None = None,
    is_dir: bool = True,
    is_socket: bool = False,
) -> Path:

    is_root: bool = os.getuid() == 0

    if not is_root and not Path(new_path).exists():
        raise AppConfigError(f"unable locate user: {owner_username}") from None

    local_path: local.LocalPath = local.path(Path(new_path))
    if not local_path.exists():
        # Set the current numeric umask and return the previous umask.
        old_umask = os.umask(0o002)
        os.setgid(grp.getgrnam("pikesquares")[2])
        try:
            if is_dir:
                local_path.mkdir()
            else:
                local_path.touch()
        finally:
            os.umask(old_umask)

    return Path(local_path)


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
    server_run_as_uid: str = pydantic.Field(default="root")
    server_run_as_gid: str = pydantic.Field(default="root")

    # DEBUG: bool = False
    data_dir: pydantic.DirectoryPath = pydantic.Field(
        default=AsyncPath("/var/lib/pikesquares"), alias="PIKESQUARES_DATA_DIR"
    )

    log_dir: pydantic.DirectoryPath = pydantic.Field(
        default=AsyncPath("/var/log/pikesquares"), alias="PIKESQUARES_LOG_DIR"
    )

    config_dir: pydantic.DirectoryPath = pydantic.Field(
        default=AsyncPath("/etc/pikesquares"), alias="PIKESQUARES_CONFIG_DIR"
    )

    run_dir: pydantic.DirectoryPath = pydantic.Field(
        default=AsyncPath("/var/run/pikesquares"), alias="PIKESQUARES_RUN_DIR"
    )
    UWSGI_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None

    SCIE_BASE: Optional[Annotated[pydantic.DirectoryPath, pydantic.Field()]] = None
    SCIE_BINDINGS: Optional[Annotated[pydantic.DirectoryPath, pydantic.Field()]] = None
    SCIE_LIFT_FILE: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None

    EASYRSA_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None
    DNSMASQ_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None
    CADDY_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None
    UV_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None
    PROCESS_COMPOSE_BIN: Optional[Annotated[pydantic.FilePath, pydantic.Field()]] = None

    CADDY_ENABLED: bool = True
    DNSMASQ_ENABLED: bool = True
    API_ENABLED: bool = True
    DEVICE_ENABLED: bool = True

    # CADDY_DIR: Optional[str] = None
    # CLI_STYLE: QuestionaryStyle

    SENTRY_DSN: pydantic.HttpUrl | None = None
    daemonize: bool = False
    ENABLE_TUNTAP_ROUTER: bool = False
    ENABLE_DIR_MONITOR: bool = False

    # to override api_settings:
    # export my_prefix_api_settings='{"foo": "x", "apple": 1}'
    # api_settings: APISettings = APISettings()

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"

    @pydantic.computed_field
    @property
    def db_path(self) -> Path:
        return ensure_system_path(self.data_dir / "pikesquares.db", is_dir=False)

    @property
    def caddy_config_path(self) -> Path:
        return ensure_system_path(self.config_dir / "caddy.json", is_dir=False)

    @property
    def caddy_config_initial(self) -> str:
        return """{"apps": {"http": {"https_port": 443, "servers": {"*.pikesquares.local": {"listen": [":443"], "routes": [{"match": [{"host": ["*.pikesquares.local"]}], "handle": [{"handler": "reverse_proxy", "transport": {"protocol": "http"}, "upstreams": [{"dial": "127.0.0.1:8035"}]}]}]}}}, "tls": {"automation": {"policies": [{"issuers": [{"module": "internal"}]}]}}}, "storage": {"module": "file_system", "root": "/var/lib/pikesquares/caddy"}}"""

    @property
    def sqlite_plugin(self) -> Path:
        return self.plugins_dir / "sqlite3_plugin.so"

    @pydantic.computed_field
    @property
    def default_app_run_as_uid(self) -> int:
        return pwd.getpwnam("pikesquares").pw_uid

    @pydantic.computed_field
    @property
    def default_app_run_as_gid(self) -> int:
        return pwd.getpwnam("pikesquares").pw_gid

    @pydantic.computed_field
    @property
    def pki_dir(self) -> Path:
        return ensure_system_path(self.data_dir / "pki")

    @pydantic.computed_field
    @property
    def uv_cache_dir(self) -> Path:
        return ensure_system_path(self.data_dir / "uv-cache")

    @pydantic.computed_field
    @property
    def pyvenvs_dir(self) -> Path:
        return ensure_system_path(self.data_dir / "pyvenvs")

    @pydantic.computed_field
    @property
    def plugins_dir(self) -> Path:
        return ensure_system_path(self.data_dir / "plugins")

    @pydantic.computed_field
    @property
    def lift_file(self) -> Path | None:
        if self.SCIE_LIFT_FILE:
            return self.SCIE_LIFT_FILE
        elif self.SCIE_BASE:
            return self.SCIE_BASE / "lift.json"

    @pydantic.field_validator("data_dir", "log_dir", "config_dir", "run_dir", mode="before")
    def ensure_paths(cls, v) -> Path:
        path = Path(v)
        ensure_system_path(path)
        return path

    """
    @pydantic.field_validator('temp_dir', mode="after")
    def validate_temp_dir(cls, v, values):
        data_dir = values.data['data_dir'] if 'data_dir' in values.data else None

        if data_dir and v.is_relative_to(data_dir):
            raise ValueError('temp_dir should not be inside data_dir')
        return v

    """

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
        try:
            return AppConfig(**override_settings)
        except pydantic.ValidationError as exc:
            logger.error(exc)
            raise AppConfigError("invalid config. giving up.")

    register_factory(context, AppConfig, conf_factory)


settings = APISettings()
