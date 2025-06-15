import structlog
import questionary
from aiopath import AsyncPath

from pikesquares.domain.runtime import AppRuntime, AppCodebase
from pikesquares.domain.python_runtime import PythonAppRuntime
from pikesquares.service_layer.uow import UnitOfWork
from .prompt_utils import gather_repo_details_and_clone

logger = structlog.getLogger()


async def provision_python_app_runtime(
    version: str,
    uow: UnitOfWork,
    custom_style: questionary.Style
) -> PythonAppRuntime | None:

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
    logger.info(f"using existing Python {version} App Runtime")
    return python_app_runtime

async def provision_app_codebase(
    launch_service: str,
    pyapps_dir: AsyncPath,
    uow: UnitOfWork,
    custom_style: questionary.Style,
) -> AppCodebase | None:
    """
      set app root dir
      set app repo dir
      clone repo into app repo dir

      provision venv
        set venv dir
        validate deps
        install deps
    """
    app_name = None
    app_root_dir=None
    app_repo_dir=None
    repo_git_url=None
    editable_mode=True
    try:
        if launch_service == "bugsink":
            repo_git_url = "https://github.com/bugsink/bugsink.git"
            app_root_dir = AsyncPath(pyapps_dir) / launch_service
        elif launch_service == "bugsink":
            repo_git_url = "https://github.com/meshnyc/meshdb.git"
            app_root_dir = AsyncPath(pyapps_dir) / launch_service

        """
        if repo_url:
            giturl = giturlparse.parse(repo_url)
            app_name = giturl.name

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

        app_repo_dir = await gather_repo_details_and_clone(
            app_name,
            repo_git_url,
            app_root_dir,
            pyapps_dir,
            custom_style,
        )
        app_pyvenv_dir = app_repo_dir / ".venv"
        app_codebase = await uow.app_codebases.get_by_root_dir(app_root_dir)
        if not app_codebase:
            app_codebase = await uow.app_codebases.add(
                AppCodebase(
                    root_dir=str(app_root_dir),
                    repo_dir=str(app_repo_dir),
                    repo_git_url=repo_git_url,
                    venv_dir=str(app_pyvenv_dir),
                    editable_mode=editable_mode,
                )
            )
            logger.info(f"created App Codebase @ {app_root_dir}")
            return app_codebase
    except Exception as exc:
        logger.info(f"failed provisioning App Codebase @ {app_root_dir}")
        logger.exception(exc)
        raise exc

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
