from .markers import hook_spec


class AttachedDaemonHookSpec:
    """
    Attached Daemon Hook Specification
    """

    @hook_spec(firstresult=True)
    def attached_daemon_collect_command_arguments(self) -> None:
        ...

    @hook_spec(firstresult=True)
    def attached_daemon_ping(self) -> bool:
        ...

    @hook_spec(firstresult=True)
    def attached_daemon_stop(self) -> bool:
        ...


class AppRuntimeHookSpec:
    """
    App Runtime Hook Specification
    """

    @hook_spec(firstresult=True)
    def app_runtime_prompt_for_version(self) -> str:
        ...
