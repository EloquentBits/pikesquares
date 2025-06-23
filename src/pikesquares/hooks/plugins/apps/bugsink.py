import structlog
from aiopath import AsyncPath

from pikesquares.exceptions import UvCommandExecutionError
from pikesquares.hooks.markers import hook_impl
from pikesquares.service_layer.uv import uv_cmd

logger = structlog.getLogger()


async def uv_run_cmd(
    uv_bin: AsyncPath,
    chdir: AsyncPath,
    cmd_args: list[str],
    cmd_env: dict | None = None
) -> tuple[str, str, str]:
    try:
        retcode, stdout, stderr = await uv_cmd(
            AsyncPath(uv_bin),
            [
                "run",
                "--verbose",
                "--python",
                "/usr/bin/python3",
                "--color",
                "never",
                *cmd_args,
            ],
            cmd_env=cmd_env or {},
            chdir=chdir,
        )
        return retcode, stdout, stderr
    except UvCommandExecutionError as exc:
        logger.error(f"failed: uv run {' '.join(cmd_args)}")
        raise exc


class Bugsink:

    @hook_impl
    async def get_repo_url(self, service_name: str) -> str | None:
        logger.debug(f"Bugsink: get_repo_url: {service_name=}")
        if service_name == "bugsink":
            return "https://github.com/bugsink/bugsink.git"

    @hook_impl
    async def get_wsgi_file(
            self,
            service_name: str,
            repo_dir: AsyncPath,
    ) -> AsyncPath | None:
        if service_name != "bugsink":
            return

        return repo_dir / "bugsink" / "wsgi.py"

    @hook_impl
    async def get_wsgi_module(
            self,
            service_name: str,
    ) -> str | None:
        if service_name != "bugsink":
            return

        return "application"

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
    ) -> bool:
        if service_name != "bugsink":
            return False

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
            "--noinput",
        ]
        cmd_db_migrate_snappea = [
            "bugsink-manage",
            "migrate",
            "--database=snappea",
            "--noinput",
        ]
        cmd_createsuperuser = [
            "bugsink-manage",
            "createsuperuser",
            "--email",
            "admin@bugsink.pikesquares.local",
            "--noinput",
            "--no-color",
            "--skip-checks",
            "--traceback",
        ]
        cmd_check_migrations = [
            "bugsink-manage",
            "check_migrations",
        ]
        cmd_check_migrations = [
            "bugsink-manage",
            "check",
            "--deploy",
            "--fail-level",
            "WARNING",
        ]

        #uv run bugsink-runsnappea



        for cmd_args in (
            cmd_create_conf,
            cmd_db_migrate,
            cmd_db_migrate_snappea,
            cmd_createsuperuser,
            cmd_check_migrations,
        ):
            cmd_env = None
            if "createsuperuser" in cmd_args:
                 cmd_env = {
                    "DJANGO_SUPERUSER_USERNAME": "admin",
                    "DJANGO_SUPERUSER_PASSWORD": "secret",
                }
            try:
                retcode, stdout, stderr  = await uv_run_cmd(
                    uv_bin=uv_bin,
                    chdir=repo_dir,
                    cmd_args=cmd_args,
                    cmd_env=cmd_env
                )
                if "createsuperuser" in cmd_args:
                    if stdout.strip() != "Superuser created successfully.":
                        raise RuntimeError("bugsink-manage unable to create a Superuser")

            except UvCommandExecutionError as exc:
                return False

        return True

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
        #EOF
        #print(p1.sentry_key)
