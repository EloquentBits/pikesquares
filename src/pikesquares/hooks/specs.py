from aiopath import AsyncPath

from .markers import hook_spec


# FIXME
# firstresult=True
# https://github.com/simonsobs/apluggy/issues/35


class AttachedDaemonHookSpec:
    """
    Attached Daemon Hook Specification
    """

    @hook_spec(firstresult=False)
    def attached_daemon_collect_command_arguments(self) -> None:
        ...

    @hook_spec(firstresult=False)
    def attached_daemon_ping(self) -> bool:
        ...

    @hook_spec(firstresult=False)
    def attached_daemon_stop(self) -> bool:
        ...


class AppRuntimeHookSpec:
    """
    App Runtime Hook Specification
    """

    @hook_spec(firstresult=False)
    def app_runtime_prompt_for_version(self) -> str:
        ...


class AppCodebaseHookSpec:
    """
    App Codebase Hook Specification
    """

    @hook_spec(firstresult=False)
    async def get_repo_url(self, service_name: str) -> str:
        ...

class PythonAppCodebaseHookSpec:
    """
    Python App Codebase Hook Specification
    """

    @hook_spec(firstresult=False)
    async def before_dependencies_install(
            self,
            service_name: str,
            uv_bin: AsyncPath,
            repo_dir: AsyncPath,
    ) -> None:
        ...

    @hook_spec(firstresult=False)
    async def after_dependencies_install(
            self,
            service_name: str,
            uv_bin: AsyncPath,
            repo_dir: AsyncPath,
    ) -> None:
        ...


class WSGIPythonAppCodebaseHookSpec:
    """
    Python App Codebase Hook Specification
    """

    @hook_spec(firstresult=False)
    async def get_wsgi_file(
            self,
            service_name: str,
            repo_dir: AsyncPath,
    ) -> AsyncPath | None:
        ...

    @hook_spec(firstresult=False)
    async def get_wsgi_module(
            self,
            service_name: str,
    ) -> str | None:
        ...
