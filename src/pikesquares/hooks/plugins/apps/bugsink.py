import structlog
from aiopath import AsyncPath
from plumbum import ProcessExecutionError

from pikesquares.exceptions import UvCommandExecutionError
from pikesquares.hooks.markers import hook_impl
from pikesquares.service_layer.uv import uv_cmd

logger = structlog.getLogger()


async def uv_run_cmd(
    uv_bin: AsyncPath,
    chdir: AsyncPath,
    cmd_args: list[str],
    cmd_env: dict | None = None
):
    logger.info(f"failed: uv run {' '.join(cmd_args)}")
    try:
        retcode, stdout, stderr = await uv_cmd(
            AsyncPath(uv_bin),
            [
                "run",
                "--verbose",
                "--python",
                "/usr/bin/python3",
                "--color", "never",
                *cmd_args,
            ],
            cmd_env=cmd_env,
            chdir=chdir,
        )
        return retcode, stdout, stderr
    except ProcessExecutionError as exc:
        logger.exception(exc)
        raise UvCommandExecutionError(f"uv run {' '.join(cmd_args)}")



class Bugsink:

    @hook_impl
    async def get_repo_url(self, service_name: str) -> str | None:
        logger.debug(f"Bugsink: get_repo_url: {service_name=}")
        if service_name == "bugsink":
            return "https://github.com/bugsink/bugsink.git"

    @hook_impl
    async def before_dependencies_install(
        self,
        service_name: str,
        uv_bin: AsyncPath,
        repo_dir: AsyncPath,
    ) -> None:
        if service_name != "bugsink":
            return

        logger.info("Bugsink before_dependencies_install")

    @hook_impl
    async def after_dependencies_install(
        self,
        service_name: str,
        uv_bin: AsyncPath,
        repo_dir: AsyncPath,
    ) -> None:
        if service_name != "bugsink":
            return

        logger.info("Bugsink after_dependencies_install")

        # uv run bugsink-show-version
        cmd_create_conf = [
            "bugsink-create-conf",
            "--template=singleserver",
            "--host=bugsink.pikesquares.local",
            f"--base-dir={repo_dir}",
        ]
        cmd_db_migrate = [
                "bugsink-manage",
                "migrate",
            ]
        cmd_db_migrate_snappea = [
            "bugsink-manage",
            "migrate",
            "--database=snappea",
        ]
        cmd_createsuperuser = [
            "bugsink-manage",
            "createsuperuser",
            "",
        ]
        #uv run bugsink-runsnappea

        for cmd_args in (
            cmd_create_conf,
            cmd_db_migrate,
            cmd_db_migrate_snappea,
            cmd_createsuperuser,
        ):
            try:
                retcode, stdout, stderr = await uv_run_cmd(
                    uv_bin=uv_bin,
                    chdir=repo_dir,
                    cmd_args=cmd_args,
                    #cmd_env
                )
                if stdout:
                    print(stdout)
            except Exception as exc:
                logger.exception("unable to run app init command")
                raise exc
        #    /new
        #csrfmiddlewaretoken PIym56UZ7PBxq2htBU1JZzMgri5yJhivqgI6ifF4HmGIlRvzpwTLuA6qQhz17SjH
        #team 464d797d-55c2-4e78-8489-eb7dbf7c09e4
        #name test
        #visibility 99
        #retention_max_event_count 10000
        #action invite
        #uv run bugsink-manage shell <<EOF

        #from projects.models import Project
        #from teams.models import Team
        #t = Team.objects.first()
        #p1 = Project.objects.create(team=Team.objects.first(), name="123123123", visibility=99, retention_max_event_count=10000)
        #print(p1.sentry_key)
        #EOF




