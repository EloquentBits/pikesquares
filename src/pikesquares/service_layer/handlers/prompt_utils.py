import traceback
from pathlib import Path

import git
import giturlparse
import questionary
import typer
import tenacity
import structlog
from aiopath import AsyncPath

from pikesquares.cli.console import console
from pikesquares.conf import AppConfigError
from pikesquares.domain.base import ServiceBase
from pikesquares.domain.device import Device
from pikesquares.domain.managed_services import AttachedDaemon
from pikesquares.domain.project import Project
from pikesquares.service_layer.uow import UnitOfWork


logger = structlog.getLogger()


class NameValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a value",
                cursor_position=len(document.text),
            )


#def get_repo_name_from_url(repo_url):
#    str_pattern = ["([^/]+)\\.git$"]
#    for i in range(len(str_pattern)):
#        pattern = re.compile(str_pattern[i])
#        matcher = pattern.search(repo_url)
#        if matcher:
#            return matcher.group(1)


class RepoAddressValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a repo url",
                cursor_position=len(document.text),
            )

        if not giturlparse.validate(document.text):
            raise questionary.ValidationError(
                message="Please enter a valid repo url",
                cursor_position=len(document.text),
            )


class PathValidator(questionary.Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise questionary.ValidationError(
                message="Please enter a value",
                cursor_position=len(document.text),
            )
        if not Path(document.text).exists():
            raise questionary.ValidationError(
                message="Please enter an existing directory to clone your git repository into",
                cursor_position=len(document.text),
            )


async def prompt_for_launch_service(uow: UnitOfWork, custom_style) -> str | None:

    try:
        launch_service = await questionary.select(
            "Select an app or a managed, self-hosted service to launch: ",
            choices=[
                questionary.Choice("Python/WSGI (new app)", value="python-wsgi-new"),
                questionary.Choice("Python/WSGI (from git repo)", value="python-wsgi-git"),
                questionary.Separator(),
                #questionary.Choice("Django (empty)", value="python-wsgi-django"),
                #questionary.Choice("Flask (empty)", value="python-wsgi-flask"),
                #questionary.Separator(),
                questionary.Choice("Bugsink (Django)", value="bugsink"),
                questionary.Choice("MeshDB (Django)", value="meshdb"),
                questionary.Separator(),
                questionary.Choice("PostgreSQL", value="postgres"),
                questionary.Choice("Redis", value="redis"),
                questionary.Separator(),
                questionary.Choice("ruby/Rack", disabled="coming soon"),
                questionary.Choice("PHP", disabled="coming soon"),
                questionary.Choice("perl/PSGI", disabled="coming soon"),
            ],
            style=custom_style,
        ).unsafe_ask_async()

        return launch_service

    except KeyboardInterrupt:
        console.info("selection cancelled.")
        raise typer.Exit(0) from None


async def prompt_base_dir(repo_name: str, custom_style: questionary.Style) -> AsyncPath:
    return await questionary.path(
            f"Choose a directory to clone your `{repo_name}` git repository into: ",
        default=str(await AsyncPath.cwd()),
        only_directories=True,
        style=custom_style,
        validate=PathValidator,
    ).unsafe_ask_async()


async def prompt_repo_url(custom_style: questionary.Style) -> str:
    repo_url_q = questionary.text(
            "Enter your app git repository url:",
            default="",
            instruction="""\nExamples:\n    https://host.xz/path/to/repo.git\n    ssh://host.xz/path/to/repo.git\n>>>""",
            style=custom_style,
            validate=RepoAddressValidator,
    )
    if not repo_url_q:
        raise typer.Exit(0) from None
    return await repo_url_q.unsafe_ask_async()


class CloneProgress(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=""):
        # console.info(f"{op_code=} {cur_count=} {max_count=} {message=}")
        if message:
            console.info(f"Completed git clone {message}")


async def gather_repo_details(
    app_name: str | None,
    repo_git_url: str | None,
    app_root_dir: AsyncPath | None,
    pyapps_dir: AsyncPath,
    custom_style: questionary.Style,
    ) -> tuple[str, str, Path]:
    """
    prompt for repo git url
    prompt for app root dir
    compose clone into dir
    """
    #clone_into_dir = AsyncPath(base_dir) / giturl.name

    repo_url = repo_git_url or await prompt_repo_url(custom_style)
    giturl = giturlparse.parse(repo_url)
    app_name = app_name or giturl.name
    app_root_dir = app_root_dir or await prompt_base_dir(giturl.name, custom_style)

    clone_into_dir = AsyncPath(app_root_dir) / app_name / app_name
    print(f"{clone_into_dir=}")

    if await clone_into_dir.exists():
        #and any(await clone_into_dir.glob("*")):
        #import ipdb;ipdb.set_trace()
        clone_into_dir_files = [path async for path in clone_into_dir.glob('**/*')]
        print(clone_into_dir_files)
        #await clone_into_dir.glob("*")
        if clone_into_dir / ".git" in clone_into_dir_files:
            if not await questionary.confirm(
                f"There appears to be a git repository already cloned in {clone_into_dir}. Chose another directory?",
                default=True,
                auto_enter=True,
                style=custom_style,
            ).unsafe_ask_async():
                raise typer.Exit(0) from None

            return giturl.name, repo_url, await prompt_base_dir(giturl.name, custom_style)

        elif len(clone_into_dir_files):
            if not await questionary.confirm(
                f"Directory {str(clone_into_dir)} is not emptry. Continue?",
                default=True,
                auto_enter=True,
                style=custom_style,
            ).unsafe_ask_async():
                raise typer.Exit(0) from None

    return repo_url, giturl.name, clone_into_dir


async def gather_repo_details_and_clone(
    app_name: str | None,
    repo_git_url: str | None,
    app_root_dir: AsyncPath | None,
    pyapps_dir: AsyncPath,
    custom_style: questionary.Style
) -> tuple[AsyncPath, str]:
    repo = None
    repo_url, _, clone_into_dir = await gather_repo_details(
        app_name,
        repo_git_url,
        app_root_dir,
        pyapps_dir,
        custom_style,
    )

    def try_again_q(instruction):
        return questionary.confirm(
                "Try entring a different repository url?",
                instruction=instruction,
                default=True,
                auto_enter=True,
                style=custom_style,
        )
    #with console.status(f"cloning `{repo_name}` repository into `{clone_into_dir}`", spinner="earth"):
    try:
        while not repo:
            try:
                repo = git.Repo.clone_from(
                    repo_url,
                    clone_into_dir,
                    progress=CloneProgress()
                )
            except git.GitCommandError as exc:
                if "already exists and is not an empty directory" in exc.stderr:
                    if await questionary.confirm(
                            "Continue with this directory?",
                            instruction=f"A git repository exists at {clone_into_dir}",
                            default=True,
                            auto_enter=True,
                            style=custom_style,
                            ).unsafe_ask_async():
                        break
                    #base_dir = prompt_base_dir(repo_name, custom_style)
                elif "Repository not found" in exc.stderr:
                    if await try_again_q(
                        f"Unable to locate a git repository at {repo_url}"
                    ).unsafe_ask_async():
                        await gather_repo_details_and_clone(
                            app_name,
                            repo_git_url,
                            app_root_dir,
                            pyapps_dir,
                            custom_style,
                        )
                    raise typer.Exit(0) from None
                else:
                    console.warning(traceback.format_exc())
                    console.warning(f"{exc.stdout}")
                    console.warning(f"{exc.stderr}")
                    if try_again_q(f"Unable to clone the provided repository url at {repo_url} into {clone_into_dir}").ask():
                        await gather_repo_details_and_clone(
                            app_name,
                            repo_git_url,
                            app_root_dir,
                            pyapps_dir,
                            custom_style
                        )
            
    except Exception as exc:
        logger.info(f"failed provisioning App Codebase @ {app_root_dir}")
        logger.exception(exc)
        print(traceback.format_exc())
        raise exc
    return AsyncPath(clone_into_dir), repo_url


async def prompt_for_project(uow: UnitOfWork, custom_style) -> Project | None:

    machine_id = await ServiceBase.read_machine_id()
    device = await uow.devices.get_by_machine_id(machine_id)
    if not device:
        raise AppConfigError("no device found in context")

    projects = await device.awaitable_attrs.projects
    if not len(projects):
        return
    elif len(projects) == 1:
        return projects[0]
    try:
        selected_project_id = await questionary.select(
            "Select an existing project: ",
            choices=[
                questionary.Choice(
                    project.name, value=project.id
                ) for project in await device.awaitable_attrs.projects
            ],
            style=custom_style,
        ).unsafe_ask_async()
    except KeyboardInterrupt as exc:
        raise exc

    if not selected_project_id:
        console.warning("no project selected")
        return

    project = await uow.projects.get_by_id(selected_project_id)
    if not project:
        console.warning(f"Unable to locate project by id {selected_project_id}")
        return

    return project

async def prompt_for_attached_daemons(
    uow: UnitOfWork,
    project: Project,
    custom_style: questionary.Style,
    is_running: bool = True,
    ) -> list[AttachedDaemon] | None:

    daemons = await project.awaitable_attrs.attached_daemons
    if not daemons:
        console.success("Appears there have been no managed services created in this project yet.")
        return

    async def check_status(daemon: AttachedDaemon) -> str:
        try:
            if bool(await daemon.read_stats()):
                return "running"
        except tenacity.RetryError:
            pass
        return "stopped"

    try:
        selected_daemons = []
        choices = []
        for daemon in daemons:
            status = await check_status(daemon)
            logger.info(f"{daemon.name} [{daemon.service_id}] {is_running=} {status=}")
            if (status == "running" and is_running) or \
                (status == "stopped" and not is_running):
                title = f"{daemon.name.capitalize()} [{daemon.service_id}] in {project.name} [{project.service_id}]"
                choices.append(
                    questionary.Choice(title, value=daemon.id, checked=True)
                )
        logger.info(choices)
        if not choices:
            return

        for daemon_id in await questionary.checkbox(
            "Select running managed services to stop: ",
            choices=choices,
            style=custom_style,
        ).unsafe_ask_async():
            daemon = await uow.attached_daemons.get_by_id(daemon_id)
            if daemon:
                selected_daemons.append(daemon)

        return selected_daemons

    except Exception as exc:
        raise exc

