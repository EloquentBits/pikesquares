# FIXME
# https://github.com/simonsobs/apluggy/issues/35
#
"""

class AHook:
    def __init__(self, pm: PluginManager_) -> None:
        self.pm = pm

    def __getattr__(self, name: str) -> Callable[..., Coroutine[Any, Any, list]]:
        async def call(*args: Any, **kwargs: Any) -> list:
            hook: HookCaller = getattr(self.pm.hook, name)
            coros: list[asyncio.Future] = hook(*args, **kwargs)
            if not isinstance(coros, Coroutine):
                return None
            if not isinstance(coros, list):  # Added an isinstance check to see whether a list or a single element is returned
                return await coros
            return await asyncio.gather(*coros)
        return call
"""
