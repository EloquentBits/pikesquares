import structlog

from pikesquares.domain.runtime import AppRuntime, AppCodebase
from pikesquares.domain.python_runtime import PythonAppRuntime
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


async def provision_python_app_runtime(
    version: str,
    uow: UnitOfWork,
) -> AppRuntime | None:

    try:
        python_app_runtime = await uow.python_app_runtimes.get_by_version(version)
        if not python_app_runtime:
            python_app_runtime = await uow.python_app_runtimes.add(
                PythonAppRuntime(version=version)
            )
            logger.info(f"created Python App Runtime {python_app_runtime.version}")
            return python_app_runtime
    except Exception as exc:
        logger.exception(exc)
        logger.info(f"failed provisioning Python App Runtime {version}")
        raise exc

    return python_app_runtime


