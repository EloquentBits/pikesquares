from glob import glob
from pathlib import Path

import structlog_sentry_logger

from pikesquares.hooks.markers import hook_impl

logger = structlog_sentry_logger.getLogger()


class GenericWSGI:
    # @hook_impl
    # def get_repo_url(self, service_name: str) -> str | None:
    #    logger.debug(f"GenericWSGI: {service_name=}")
    #    if service_name == "GenericWSGI":
    #        return "https://github.com/bugsink/bugsink.git"

    @hook_impl
    def get_wsgi_files(
        self,
        service_name: str,
        root_dir: Path,
    ) -> list[Path] | None:
        if service_name != "GenericWSGI":
            return

        wsgi_files = [Path(f) for f in glob(f"{root_dir}/**/*wsgi*.py", recursive=True) if "tests" not in f]
        logger.info(f"{wsgi_files}")
        return wsgi_files

    @hook_impl
    def get_wsgi_module(
        self,
        service_name: str,
    ) -> str | None:
        if service_name != "GenericWSGI":
            return
        wsgi_module = None

        return wsgi_module or "application"
