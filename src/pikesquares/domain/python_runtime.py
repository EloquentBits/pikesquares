import structlog

logger = structlog.getLogger()

from .runtime import hook_impl



class PythonRuntime:
    """
    App Runtime Plugin
    """

    @hook_impl
    def prompt_for_version(self) -> str:
        print("prompt for version")
        return "3.12"

