from pathlib import Path


import structlog
import cuid
from aiopath import AsyncPath

from pikesquares.domain.wsgi_app import WsgiApp
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.domain.project import Project
from pikesquares.domain.router import HttpRouter
from pikesquares.services.apps.exceptions import DjangoSettingsError
from pikesquares.exceptions import StatsReadError
from pikesquares.services.apps.python import PythonRuntime
from pikesquares.services.apps.django import PythonRuntimeDjango, DjangoSettings
from pikesquares.service_layer.handlers.monitors import create_or_restart_instance
from pikesquares.service_layer.handlers.routers import create_tuntap_device
from pikesquares.service_layer.handlers.routers import tuntap_router_next_available_ip

from pikesquares.presets.wsgi_app import WsgiAppSection


logger = structlog.getLogger()


async def provision_wsgi_app(
    name: str,
    app_root_dir: AsyncPath,
    app_repo_dir: AsyncPath,
    app_pyvenv_dir: AsyncPath,
    uv_bin: Path,
    uow: UnitOfWork,
    project: Project,
    # routers: list[Router],
) -> WsgiApp | None:

    try:

        wsgi_app = await uow.wsgi_apps.get_by_name(name)

        runtime_base = PythonRuntime
        py_kwargs = {
            "app_root_dir": app_root_dir,
            "app_repo_dir": app_repo_dir,
            "app_pyvenv_dir": app_pyvenv_dir,
            "uv_bin": uv_bin,
            # "rich_live": live,
        }
        # console.info(py_kwargs)
        if PythonRuntime.is_django(app_repo_dir):
            runtime = PythonRuntimeDjango(**py_kwargs)
        else:
            runtime = runtime_base(**py_kwargs)

        cmd_env = {
            # "UV_CACHE_DIR": str(conf.pv_cache_dir),
            "UV_PROJECT_ENVIRONMENT": runtime.app_pyvenv_dir,
        }
        #try:
        #    runtime.create_venv(Path(runtime.app_pyvenv_dir), cmd_env=cmd_env)
        #except Exception as exc:
        #    logger.exception("unable to create venv")
        #    raise exc
        #
        if not await runtime.app_pyvenv_dir.exists():
            try:
                runtime.install_dependencies(venv=runtime.app_pyvenv_dir)
            except Exception as exc:
                logger.exception("unable to install dependencies")
                raise exc

        if name == "bugsink":
            if 0:
                # uv run bugsink-show-version
                cmd_create_conf = [
                    "bugsink-create-conf",
                    "--template=singleserver",
                    "--host=bugsink.pikesquares.local",
                    f"--base-dir={app_root_dir}",
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
                        retcode, stdout, stderr = runtime.run_app_init_command(cmd_args)
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


        if isinstance(runtime, PythonRuntimeDjango):
            django_settings = DjangoSettings(
                settings_module ="bugsink_conf",
                root_urlconf = "bugsink.urls",
                wsgi_application = "bugsink.wsgi.application",
            )
            django_settings = django_settings or runtime.collected_project_metadata.get("django_settings")
            if not django_settings:
                raise DjangoSettingsError("unable to detect django settings")

            logger.debug(django_settings.model_dump())
            if 0:
                django_check_messages = runtime.collected_project_metadata.get("django_check_messages", [])

                for msg in django_check_messages.messages:
                    logger.debug(f"{msg.id=}")
                    logger.debug(f"{msg.message=}")

            wsgi_parts = django_settings.wsgi_application.split(".")[:-1]
            wsgi_file = AsyncPath(runtime.app_repo_dir) / AsyncPath("/".join(wsgi_parts) + ".py")
            wsgi_module = django_settings.wsgi_application.split(".")[-1]

        if not all([wsgi_file, wsgi_module]):
            logger.info("unable to detect all the wsgi required settings.")
            return

        if not wsgi_app:
            service_type = "WSGI-App"
            wsgi_app = WsgiApp(
                service_id=f"{service_type.lower() }-{cuid.slug()}",
                name=name,
                run_as_uid="pikesquares",
                run_as_gid="pikesquares",
                project=project,
                uwsgi_plugins="tuntap;forkptyrouter",
                root_dir=str(runtime.app_repo_dir),
                wsgi_file=str(wsgi_file),
                wsgi_module=wsgi_module,
            )
            await uow.wsgi_apps.add(wsgi_app)

            tuntap_routers = await uow.tuntap_routers.get_by_project_id(project.id)
            if tuntap_routers:
                ip = tuntap_router_next_available_ip(tuntap_routers[0])
                await create_tuntap_device(uow, tuntap_routers[0], ip, wsgi_app.service_id)

    except Exception as exc:
        raise exc

    return wsgi_app

async def up(
        uow: UnitOfWork,
        wsgi_app: WsgiApp,
        project: Project,
        http_router: HttpRouter,
        console,
    ):
    project = await http_router.awaitable_attrs.project
    tuntap_routers = await project.awaitable_attrs.tuntap_routers
    #tuntap_routers = await uow.tuntap_routers.get_by_project_id(project.id)
    if not tuntap_routers:
        raise Exception(f"could not locate tuntap routers for project {project.name} [{project.id}]")

    tuntap_router  = tuntap_routers[0]
    wsgi_app_device = await uow.tuntap_devices.get_by_linked_service_id(wsgi_app.service_id)

    section = WsgiAppSection(wsgi_app)
    section._set("jailed", "true")
    # forkpty
    section._set("unshared", "true")
    section.main_process.run_command_on_event(
        command=f"hostname {wsgi_app.service_id}",
        phase=section.main_process.phases.PRIV_DROP_PRE
    )

    router_tuntap = section.routing.routers.tuntap().device_connect(
        device_name=wsgi_app_device.name,
        socket=tuntap_router.socket_address,
    )
    #.device_add_rule(
    #    direction="in",
    #    action="route",
    #    src=tuntap_router.ip,
    #    dst=http_router_tuntap_device.ip,
    #    target="10.20.30.40:5060",
    #)
    section.routing.use_router(router_tuntap)

    router_forkpty = section.routing.routers.forkpty(
        on=AsyncPath(wsgi_app.run_dir) / f"{wsgi_app.service_id}-forkptyrouter.socket",
        undeferred=True
    ).set_basic_params(
        run_command="/bin/zsh"
    ).set_connections_params(
        timeout_socket=13
    ).set_window_params(cols=10, rows=15)

    section.routing.use_router(router_forkpty)

    #; bring up loopback
    #exec-as-root = ifconfig lo up
    section.main_process.run_command_on_event(
        command="ifconfig lo up",
        phase=section.main_process.phases.PRIV_DROP_PRE,
    )
    # bring up interface uwsgi0
    #exec-as-root = ifconfig uwsgi0 192.168.0.2 netmask 255.255.255.0 up
    section.main_process.run_command_on_event(
        command=f"ifconfig {wsgi_app_device.name} {wsgi_app_device.ip} netmask {wsgi_app_device.netmask} up",
        phase=section.main_process.phases.PRIV_DROP_PRE,
    )
    # and set the default gateway
    #exec-as-root = route add default gw 192.168.0.1
    section.main_process.run_command_on_event(
        command=f"route add default gw {tuntap_router.ip}",
        phase=section.main_process.phases.PRIV_DROP_PRE
    )
    section.main_process.run_command_on_event(
        command=f"ping -c 1 {tuntap_router.ip}",
        phase=section.main_process.phases.PRIV_DROP_PRE,
    )
    section.main_process.run_command_on_event(
        command="route -n",
        phase=section.main_process.phases.PRIV_DROP_PRE,
    )
    section.main_process.run_command_on_event(
        command="ping -c 1 8.8.8.8",
        phase=section.main_process.phases.PRIV_DROP_PRE,
    )

    if not all([
        http_router.subscription_server_address.exists(),
        http_router.subscription_server_address.is_socket()]):
        raise Exception("http router subscription server is not available")

    section.subscriptions.subscribe(
        server=http_router.subscription_server_address,
        address=str(wsgi_app.socket_address),  # address and port of wsgi app
        key=f"{wsgi_app.name}.pikesquares.local" ,
    )
    section.subscriptions.set_server_params(
        client_notify_address=wsgi_app.subscription_notify_socket,
    )

    #section._set("env","REQUESTS_CA_BUNDLE=/var/lib/pikesquares/pikesquares-ca.pem")
    if 0:
        section.master_process.attach_process(
            command="/usr/bin/redis-server /etc/pikesquares/redis.conf",
            for_legion=False,
            broken_counter=3,
            #pidfile="/var/run/pikesquares/redis-server.pid",
            control=False,
            daemonize=True,
            touch_reload="/etc/pikesquares/redis.conf",
            signal_stop=15,
            signal_reload=15,
            honour_stdin=0,
            uid="pikesquarees",
            gid="pikesquarees",
            new_pid_ns=0,
            change_dir="/var/lib/pikesquares/redis",
        )

    try:
        _ = WsgiApp.read_stats(wsgi_app.stats_address)
    except StatsReadError:
        console.success(f":heavy_check_mark:     Launching WSGI App {wsgi_app.name} [{wsgi_app.service_id}]. Done!")

        #print(section.as_configuration().format())
        project_zmq_monitor = await project.awaitable_attrs.zmq_monitor
        project_zmq_monitor_address  = project_zmq_monitor.zmq_address
        #print(f"launching wsgi app in {project_zmq_monitor.zmq_address}")
        await create_or_restart_instance(
            project_zmq_monitor_address,
            f"{wsgi_app.service_id}.ini",
            section.as_configuration().format(do_print=True),
        )
        #await project.zmq_monitor.create_or_restart_instance(f"{wsgi_app.service_id}.ini", wsgi_app, project.zmq_monitor)
