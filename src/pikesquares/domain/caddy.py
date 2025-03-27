
import structlog
from plumbum import ProcessExecutionError

from pikesquares.domain.managed_services import ManagedServiceBase
from pikesquares.services.base import ServiceUnavailableError

logger = structlog.get_logger()


class CaddyUnavailableError(ServiceUnavailableError):
    pass


class Caddy(ManagedServiceBase):

    daemon_name: str = "caddy"

    cmd_args: list[str] = []
    cmd_env: dict[str, str] = {}

    # "${CADDY_BIN} reverse-proxy --from :2080 --to :8034"

    def __repr__(self) -> str:
        return "caddy"

    def __str__(self) -> str:
        return self.__repr__()

    def up(self) -> tuple[int, str, str]:
        cmd_args = [
            "reverse-proxy",
            "--from",
            ":2080",
            "--to",
            ":8034",
        ]
        cmd_env = {}
        try:
            return self.cmd(
                cmd_args,
                cmd_env=cmd_env,
            )

        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr

    def down(self) -> tuple[int, str, str]:

        try:
            cmd_args = []
            cmd_env = {}
            return self.cmd(
                cmd_args,
                cmd_env=cmd_env,
            )
        except ProcessExecutionError as exc:
            logger.error(exc)
            return exc.retcode, exc.stdout, exc.stderr
