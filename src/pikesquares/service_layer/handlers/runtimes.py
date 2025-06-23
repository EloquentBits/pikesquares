import traceback

import apluggy as pluggy
import questionary
import structlog
from aiopath import AsyncPath

from pikesquares.domain.python_runtime import PythonAppRuntime
from pikesquares.domain.runtime import PythonAppCodebase
from pikesquares.hooks.plugins.apps.bugsink import Bugsink
from pikesquares.hooks.plugins.apps.meshdb import Meshdb
from pikesquares.service_layer.uow import UnitOfWork

from .prompt_utils import gather_repo_details_and_clone

logger = structlog.getLogger()


async def provision_python_app_runtime(
    version: str,
    uow: UnitOfWork,
    custom_style: questionary.Style
) -> PythonAppRuntime | None:

    async with uow:
        try:
            runtime =  await uow.python_app_runtimes.get_by_version(version)
            if not runtime:
                runtime = await uow.python_app_runtimes.add(PythonAppRuntime(version=version))
                await uow.commit()
            return runtime
        except Exception as exc:
            logger.exception(exc)
            logger.info(f"failed provisioning Python App Runtime {version}")
            await uow.rollback()
            raise exc

async def provision_app_codebase(
    service_name: str,
    plugin_manager: pluggy.PluginManager,
    pyapps_dir: AsyncPath,
    uv_bin: AsyncPath,
    uow: UnitOfWork,
    custom_style: questionary.Style,
) -> PythonAppCodebase | None:
    """
      set app root dir
      set app repo dir
      clone repo into app repo dir

      provision venv
        set venv dir
        validate deps
        install deps
    """
    app_name = service_name
    app_codebase = None
    app_root_dir=None
    app_repo_dir=None
    editable_mode=True

    plugin_manager.register(Bugsink())
    plugin_manager.register(Meshdb())

    repo_git_urls: list[str] = await plugin_manager.ahook.get_repo_url(
        service_name=service_name,
    )
    app_root_dir = AsyncPath(pyapps_dir) / app_name
    """
    if not app_name:
        app_name = await questionary.text(
            "Choose a name for your app: ",
            default=randomname.get_name().lower(),
            style=custom_style,
            #validate=NameValidator,
        ).ask_async()
    """
    if app_root_dir:
        await app_root_dir.mkdir(exist_ok=True)

    app_repo_dir, repo_git_url = await gather_repo_details_and_clone(
        app_name,
        next(filter(lambda x: x, repo_git_urls)),
        app_root_dir,
        pyapps_dir,
        custom_style,
    )
    app_pyvenv_dir = app_repo_dir / ".venv"

    async with uow:
        try:
            app_codebase = await uow.python_app_codebases.get_by_root_dir(str(app_root_dir))
            if not app_codebase:
                app_codebase = await uow.python_app_codebases.add(
                    PythonAppCodebase(
                        root_dir=str(app_root_dir),
                        repo_dir=str(app_repo_dir),
                        repo_git_url=repo_git_url,
                        venv_dir=str(app_pyvenv_dir),
                        editable_mode=editable_mode,
                        uv_bin=str(uv_bin),
                    )
                )
                logger.info(f"created App Codebase @ {app_root_dir}")

            if not await app_codebase.dependencies_validate():
                raise RuntimeError("validating dependencies failed")

            logger.info(f"Successfully validated {service_name} dependencies")

            if not await app_codebase.dependencies_install(service_name, plugin_manager):
                raise RuntimeError("installing dependencies failed")

        except Exception as exc:
            logger.exception(exc)
            logger.info(f"failed provisioning Python App Codebase @ {app_root_dir}")
            print(traceback.format_exc())
            await uow.rollback()
            raise exc

        await uow.commit()

    return app_codebase

"""
def git_clone(repo_url: str, clone_into_dir: Path):
    class CloneProgress(git.RemoteProgress):
        def update(self, op_code, cur_count, max_count=None, message=""):
            # console.info(f"{op_code=} {cur_count=} {max_count=} {message=}")
            if message:
                console.info(f"Completed git clone {message}")

    clone_into_dir.mkdir(exist_ok=True)
    if not any(clone_into_dir.iterdir()):
        try:
            return git.Repo.clone_from(repo_url, clone_into_dir,  progress=CloneProgress())
        except git.GitCommandError as exc:
            logger.exception(exc)
        # if "already exists and is not an empty directory" in exc.stderr:
            pass
"""
