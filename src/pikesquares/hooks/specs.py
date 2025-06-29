import apluggy as pluggy
from aiopath import AsyncPath

from pikesquares.domain.managed_services import AttachedDaemon

from .markers import hook_spec

# FIXME
# firstresult=True
# https://github.com/simonsobs/apluggy/issues/35


class AttachedDaemonHookSpec:
    """
    Attached Daemon Hook Specification
    """

    @hook_spec
    async def create_data_dir(self, service_name: str) -> bool | None:
        ...

    @hook_spec(firstresult=False)
    async def attached_daemon_collect_command_arguments(
        self,
        attached_daemon: AttachedDaemon,
        bind_ip: str,
        bind_port: int = 6379,
    ) -> dict | None:
        ...

    @hook_spec(firstresult=False)
    async def attached_daemon_ping(
        self,
        attached_daemon: AttachedDaemon,
        bind_ip: str,
        bind_port: int = 6379,
    ) -> bool | None:
        ...

    @hook_spec(firstresult=False)
    async def attached_daemon_stop(
        self,
        attached_daemon: AttachedDaemon,
        bind_ip: str,
        bind_port: int = 6379,
    ) -> bool | None:
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


def plugin_manager_factory():
    pm = pluggy.PluginManager("pikesquares")
    pm.add_hookspecs(AttachedDaemonHookSpec)
    pm.add_hookspecs(AppRuntimeHookSpec)
    pm.add_hookspecs(AppCodebaseHookSpec)
    pm.add_hookspecs(PythonAppCodebaseHookSpec)
    pm.add_hookspecs(WSGIPythonAppCodebaseHookSpec)
    return pm
