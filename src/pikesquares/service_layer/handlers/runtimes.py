import structlog

from pikesquares.domain.python_runtime import PythonAppRuntime, PythonRuntimeVersion
from pikesquares.service_layer.uow import UnitOfWork

logger = structlog.getLogger()


def delete_python_app_runtime(runtime_version: PythonRuntimeVersion, uow: UnitOfWork) -> PythonAppRuntime | None:
    # (version, path, implementation)
    logger.info(f"deleting {runtime_version.version} {runtime_version.implementation}")
    try:
        runtime = uow.python_app_runtimes.get_by_version(
            runtime_version.version, "Python", runtime_version.implementation
        )
        if runtime:
            uow.python_app_runtimes.delete(runtime.id)
            uow.commit()
        return runtime
    except Exception as exc:
        logger.exception(exc)
        logger.error(
            f"failed provisioning Python App Runtime {runtime_version.version} {runtime_version.implementation}"
        )
        uow.rollback()
        raise exc


def provision_python_app_runtime(runtime_version: PythonRuntimeVersion, uow: UnitOfWork) -> PythonAppRuntime | None:
    # (version, path, implementation)
    logger.info(f"provisioning {runtime_version.version} {runtime_version.implementation}")
    try:
        runtime = uow.python_app_runtimes.get_by_version(
            runtime_version.version, "Python", runtime_version.implementation
        )
        if not runtime:
            runtime = uow.python_app_runtimes.add(
                PythonAppRuntime(
                    version=runtime_version.version, lang="Python", implementation=runtime_version.implementation
                )
            )
            uow.commit()
        return runtime
    except Exception as exc:
        logger.exception(exc)
        logger.error(
            f"failed provisioning Python App Runtime {runtime_version.version} {runtime_version.implementation}"
        )
        uow.rollback()
        raise exc
