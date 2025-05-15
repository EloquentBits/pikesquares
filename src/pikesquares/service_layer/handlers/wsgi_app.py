from pathlib import Path


import structlog
import cuid
from aiopath import AsyncPath

from pikesquares.domain.wsgi_app import WsgiApp
from pikesquares.service_layer.uow import UnitOfWork
from pikesquares.domain.project import Project
from pikesquares.domain.router import HttpRouter
from pikesquares.services.apps.exceptions import DjangoSettingsError
from pikesquares.services.apps.python import PythonRuntime
from pikesquares.services.apps.django import PythonRuntimeDjango, DjangoSettings
from pikesquares.service_layer.handlers.monitors import create_or_restart_instance
from pikesquares.service_layer.handlers.routers import create_tuntap_device

from pikesquares.presets.wsgi_app import WsgiAppSection


logger = structlog.getLogger()


async def provision_wsgi_app(
    name: str,
    app_root_dir: AsyncPath,
    uv_bin: Path,
    uow: UnitOfWork,
    project: Project,
    # routers: list[Router],
) -> WsgiApp | None:

    try:
        runtime_base = PythonRuntime
        py_kwargs = {
            "app_root_dir": app_root_dir,
            "uv_bin": uv_bin,
            # "rich_live": live,
        }
        # console.info(py_kwargs)
        if PythonRuntime.is_django(app_root_dir):
            runtime = PythonRuntimeDjango(**py_kwargs)
        else:
            runtime = runtime_base(**py_kwargs)

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
            wsgi_file = AsyncPath(runtime.app_root_dir) / AsyncPath("/".join(wsgi_parts) + ".py")
            wsgi_module = django_settings.wsgi_application.split(".")[-1]

        if not all([wsgi_file, wsgi_module]):
            logger.info("unable to detect all the wsgi required settings.")
            return

        uwsgi_plugins = ["tuntap", "logfile"]
        service_type = "WSGI-App"
        wsgi_app = WsgiApp(
            service_id=f"{service_type.lower() }-{cuid.slug()}",
            name=name,
            run_as_uid="pikesquares",
            run_as_gid="pikesquares",
            project=project,
            uwsgi_plugins=",".join(uwsgi_plugins) if uwsgi_plugins else "",
            root_dir=str(runtime.app_root_dir),
            wsgi_file=str(wsgi_file),
            wsgi_module=wsgi_module,
        )
        await uow.wsgi_apps.add(wsgi_app)

        pyvenv_dir = app_root_dir / "../.venv"
        await pyvenv_dir.mkdir(exist_ok=True)

        logger.info(f"installing dependencies into venv @ {pyvenv_dir}")
        cmd_env = {
            # "UV_CACHE_DIR": str(conf.pv_cache_dir),
            "UV_PROJECT_ENVIRONMENT": pyvenv_dir,
        }
        try:
            runtime.create_venv(Path(pyvenv_dir), cmd_env=cmd_env)
        except Exception:
            logger.exception("unable to create venv")
        else:
            runtime.install_dependencies()

        #wsgi_app_ip = "192.168.34.2"
        tuntap_routers = await uow.tuntap_routers.get_by_project_id(project.id)
        if tuntap_routers:
            ip = tuntap_routers[0].ipv4_interface + 2
            await create_tuntap_device(uow, tuntap_routers[0], ip, wsgi_app.service_id)

    except Exception as exc:
        raise exc

    return wsgi_app

async def up(
        uow: UnitOfWork,
        wsgi_app: WsgiApp,
        project: Project,
        http_router: HttpRouter,
    ):
    project_zmq_monitor = await uow.zmq_monitors.get_by_project_id(project.id)
    tuntap_routers = await uow.tuntap_routers.get_by_project_id(project.id)

    if not tuntap_routers:
        raise Exception(f"could not locate tuntap routers for project {project.name} [{project.id}]")
    tuntap_router  = tuntap_routers[0]
    wsgi_app_device = await uow.tuntap_devices.get_by_linked_service_id(wsgi_app.service_id)

    if not await AsyncPath(project_zmq_monitor.socket).exists():
        logger.error("unable to locate project zmq monitor socket")
        raise Exception("unable to locate project zmq monitor socket")

    section = WsgiAppSection(wsgi_app)
    section._set("jailed", "true")
    router_tuntap = section.routing.routers.tuntap().device_connect(
        device_name=wsgi_app_device.name,
        socket=tuntap_router.socket,
    )
    #.device_add_rule(
    #    direction="in",
    #    action="route",
    #    src=tuntap_router.ip,
    #    dst=http_router_tuntap_device.ip,
    #    target="10.20.30.40:5060",
    #)
    section.routing.use_router(router_tuntap)

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

    section.subscriptions.subscribe(
        server=http_router.subscription_server_address,
        address=str(wsgi_app.socket_address),  # address and port of wsgi app
        key=f"{wsgi_app.name}.pikesquares.local" ,
    )
    section.subscriptions.set_server_params(
        client_notify_address=wsgi_app.subscription_notify_socket,
    )

    print(section.as_configuration().format())
    print(f"launching wsgi app in {project_zmq_monitor.zmq_address}")

    await create_or_restart_instance(
        project_zmq_monitor.zmq_address,
        f"{wsgi_app.service_id}.ini",
        section.as_configuration().format(do_print=True),
    )
    #await project.zmq_monitor.create_or_restart_instance(f"{wsgi_app.service_id}.ini", wsgi_app, project.zmq_monitor)
