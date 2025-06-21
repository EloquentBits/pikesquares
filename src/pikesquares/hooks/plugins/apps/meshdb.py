import structlog

from pikesquares.hooks.markers import hook_impl

logger = structlog.getLogger()


class Meshdb:

    @hook_impl
    async def get_repo_url(self, service_name: str) -> str | None:
        logger.debug(f"Meshdb: get_repo_url: {service_name=}")
        if service_name == "meshdb":
            return "https://github.com/meshnyc/meshdb.git"

    @hook_impl
    async def before_dependencies_install(
        self,
        service_name: str,
    ) -> None:
        if service_name != "meshdb":
            return

        logger.info("Meshdb before_dependencies_install")

    @hook_impl
    async def after_dependencies_install(
        self,
        service_name: str,
    ) -> None:
        if service_name != "meshdb":
            return

        logger.info("Meshdb after_dependencies_install")


