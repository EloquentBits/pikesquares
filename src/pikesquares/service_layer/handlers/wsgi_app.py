import traceback

import structlog
import cuid
from aiopath import AsyncPath
import tenacity
import apluggy as pluggy

from pikesquares.domain.wsgi_app import WsgiApp
from pikesquares.domain.python_runtime import PythonAppRuntime
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.domain.project import Project
from pikesquares.domain.runtime import PythonAppCodebase
from pikesquares.service_layer.handlers.monitors import create_or_restart_instance
from pikesquares.service_layer.handlers.routers import create_tuntap_device
from pikesquares.service_layer.ipaddress_utils import tuntap_router_next_available_ip
from pikesquares.presets.wsgi_app import WsgiAppSection
from pikesquares.exceptions import DjangoSettingsError

logger = structlog.getLogger()
"""
#runtime_base = PythonRuntime
#py_kwargs = {
#    "app_root_dir": app_root_dir,
#    "app_repo_dir": app_repo_dir,
#    "app_pyvenv_dir": app_pyvenv_dir,
#    "uv_bin": uv_bin,
#    # "rich_live": live,
#}
# console.info(py_kwargs)
#if PythonRuntime.is_django(app_repo_dir):
#    runtime = PythonRuntimeDjango(**py_kwargs)
#else:
#    runtime = runtime_base(**py_kwargs)

#cmd_env = {
    # "UV_CACHE_DIR": str(conf.pv_cache_dir),
#    "UV_PROJECT_ENVIRONMENT": app_codebase.venv_dir,
#}
#try:
#    runtime.create_venv(Path(runtime.app_pyvenv_dir), cmd_env=cmd_env)
#except Exception as exc:
#    logger.exception("unable to create venv")
#    raise exc
#
#if not await runtime.app_pyvenv_dir.exists():
#    try:
#        runtime.install_dependencies(venv=runtime.app_pyvenv_dir)
#    except Exception as exc:
#        logger.exception("unable to install dependencies")
#        raise exc

#if isinstance(runtime, PythonRuntimeDjango):
#    django_settings = DjangoSettings(
#        settings_module="bugsink_conf",
#        root_urlconf="bugsink.urls",
#        wsgi_application="bugsink.wsgi.application",
#    )
#    django_settings = django_settings or runtime.collected_project_metadata.get("django_settings")
#    if not django_settings:
#        raise DjangoSettingsError("unable to detect django settings")

#    logger.debug(django_settings.model_dump())
#    if 0:

#        for msg in django_check_messages.messages:
#            logger.debug(f"{msg.id=}")
#            logger.debug(f"{msg.message=}")

#    wsgi_parts = django_settings.wsgi_application.split(".")[:-1]
#    wsgi_file = AsyncPath(runtime.app_repo_dir) / AsyncPath("/".join(wsgi_parts) + ".py")
#    wsgi_module = django_settings.wsgi_application.split(".")[-1]

#if not all([wsgi_file, wsgi_module]):
#    logger.info("unable to detect all the wsgi required settings.")
#    return
"""

async def provision_wsgi_app(
        name: str,
        root_dir: AsyncPath,
        uow: UnitOfWork,
        plugin_manager: pluggy.PluginManager,
) -> WsgiApp | None:

    try:
        if not await root_dir.exists():
            raise RuntimeError(f"root dir @ {root_dir} does not exist.")

        app_codebase = await uow.python_app_codebases.get_by_root_dir(str(root_dir))
        if not app_codebase:
            raise RuntimeError(f"unable to look up {name} app codebase.")

        app_runtime = await uow.python_app_runtimes.get_by_version("3.12")
        if not app_runtime:
            raise RuntimeError(f"unable to look up {name} app runtime")

        project = await uow.projects.get_by_name(name)
        if not project:
            raise RuntimeError(f"unable to look up {name} project")

        service_type = "WSGI-App"
        wsgi_file = next(filter(lambda f: f is not None, await plugin_manager.\
            ahook.get_wsgi_file(
                service_name=name,
                repo_dir=AsyncPath(app_codebase.repo_dir),
            )))
        wsgi_module = next(filter(lambda m: m is not None, await plugin_manager.ahook.\
            get_wsgi_module(service_name=name)))
        wsgi_app = WsgiApp(
            service_id=f"{service_type.lower()}-{cuid.slug()}",
            name=name,
            run_as_uid="pikesquares",
            run_as_gid="pikesquares",
            project=project,
            python_app_runtime=app_runtime,
            python_app_codebase=app_codebase,
            uwsgi_plugins="tuntap;forkptyrouter",
            root_dir=app_codebase.root_dir,
            wsgi_file=str(wsgi_file),
            wsgi_module=wsgi_module,
            venv_dir=app_codebase.venv_dir,
        )
        await uow.wsgi_apps.add(wsgi_app)

        tuntap_routers = await uow.tuntap_routers.get_by_project_id(project.id)
        if tuntap_routers:
            ip = await tuntap_router_next_available_ip(tuntap_routers[0])
            wgsi_app_tuntap_device = await create_tuntap_device(
                uow,
                tuntap_routers[0],
                ip,
                wsgi_app.service_id
            )
            logger.info(f"created wsgi app tuntap device: {wgsi_app_tuntap_device}")
    except Exception as exc:
        logger.info(f"failed provisioning Python App {name}")
        raise exc

    return wsgi_app


async def wsgi_app_up(
        wsgi_app: WsgiApp,
        uow: UnitOfWork,
        console,
    ):

    stats = None
    while not stats:
        try:
            return await wsgi_app.read_stats()
        except tenacity.RetryError:
            break

    try:
        #wsgi_app = await uow.wsgi_apps.get_by_service_id(service_id)
        #if not wsgi_app:
        #    raise RuntimeError(f"unable to look up app by service id: {service_id}")
        app_codebase = await wsgi_app.awaitable_attrs.python_app_codebase
        #app_runtime = await wsgi_app.awaitable_attrs.python_app_runtime
        project = await wsgi_app.awaitable_attrs.project
        http_routers = await project.awaitable_attrs.http_routers
        if not http_routers:
            raise RuntimeError(f"could not locate http routers for project {project.name} [{project.id}]")

        tuntap_routers = await project.awaitable_attrs.tuntap_routers
        #tuntap_routers = await uow.tuntap_routers.get_by_project_id(project.id)
        if not tuntap_routers:
            raise RuntimeError(f"could not locate tuntap routers for project {project.name} [{project.id}]")

        tuntap_router  = tuntap_routers[0]

        wsgi_app_device = await uow.tuntap_devices.get_by_linked_service_id(wsgi_app.service_id)
        http_router = http_routers[0]

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
        if 0:
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

        #if not all([
        #    http_router.subscription_server_address.exists(),
        #    http_router.subscription_server_address.is_socket()]):
        #    raise Exception("http router subscription server is not available")

        section.subscriptions.subscribe(
            server=http_router.subscription_server_address,
            address=str(wsgi_app.socket_address),  # address and port of wsgi app
            key=f"{wsgi_app.name}.pikesquares.dev",
        )
        section.subscriptions.set_server_params(
            client_notify_address=wsgi_app.subscription_notify_socket,
        )

        #section._set("env","REQUESTS_CA_BUNDLE=/var/lib/pikesquares/pikesquares-ca.pem")
        section._set("pythonpath", app_codebase.repo_dir)

        #try:
        #    _ = await wsgi_app.read_stats()
        #except tenacity.RetryError:
        #    return False

        console.success(f":heavy_check_mark:     Launching WSGI App {wsgi_app.name} [{wsgi_app.service_id}]. Done!")
        #print(section.as_configuration().format())
        project_zmq_monitor = await project.awaitable_attrs.zmq_monitor
        project_zmq_monitor_address  = project_zmq_monitor.zmq_address
        #print(f"launching wsgi app in {project_zmq_monitor.zmq_address}")

        await create_or_restart_instance(
            project_zmq_monitor_address,
            f"{wsgi_app.service_id}.ini",
            section.as_configuration().format(do_print=False),
        )
        #await project.zmq_monitor.create_or_restart_instance(f"{wsgi_app.service_id}.ini", wsgi_app, project.zmq_monitor)

    except Exception as exc:
        logger.error("failed provisioning Python App")
        raise exc

    stats = None
    while not stats:
        try:
            return await wsgi_app.read_stats()
        except tenacity.RetryError:
            break

