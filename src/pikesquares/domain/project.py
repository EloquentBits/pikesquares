# import shutil
from functools import cached_property
from pathlib import Path

from sqlmodel import Field
from cuid import cuid
import pydantic
from aiopath import AsyncPath
import structlog

from .base import ServiceBase
from pikesquares import services
from pikesquares.conf import AppConfig, AppConfigError
from pikesquares.presets.project import ProjectSection


logger = structlog.getLogger()


class Project(ServiceBase, table=True):

    name: str = Field(default="sandbox", max_length=32)

    run_as_uid: str = Field(default="root")
    run_as_gid: str = Field(default="root")

    @property
    def uwsgi_config_section_class(self) -> ProjectSection:
        return ProjectSection

    @pydantic.computed_field
    @cached_property
    def service_config(self) -> Path:
        return Path(self.config_dir) / "projects" / f"{self.service_id}.ini"

    @pydantic.computed_field
    @cached_property
    def touch_reload_file(self) -> Path:
        return self.service_config

    @pydantic.computed_field
    @cached_property
    def apps_dir(self) -> Path:
        return Path(self.config_dir) / f"{self.service_id}" / "apps"

    def ping(self) -> None:
        print("== Project.ping ==")

    def zmq_write_config(self):
        pass
        # print("sending msg to zmq")
        # self.zmq_socket.send_multipart(
        #    [
        #        b"touch",
        #        f"{self.service_id}.json".encode(),
        #        json.dumps(self.config_json).encode(),
        #    ]
        # )
        # print("sent msg to zmq")

        # if not self.is_started() and str(self.service_config.resolve()).endswith(".stopped"):
        #    shutil.move(
        #        str(self.service_config),
        #        self.service_config.removesuffix(".stopped")
        #    )

    # stats_addr = self.config_json["uwsgi"]["emperor-stats-server"]
    # self.config_json["uwsgi"]["emperor"] = zmq_addr #uwsgi.cache_get(zmq_addr_key, self.cache).decode()
    # self.config_json["uwsgi"]["emperor"] = self.apps_dir
    # uwsgi.cache_update(f"{self.service_id}-stats-addr", str(stats_addr), 0, self.cache)
    # self.config_json["uwsgi"]["emperor-wrapper"] = \
    #    str((Path(self.conf.VIRTUAL_ENV) / "bin/uwsgi").resolve())

    # self.config_json["uwsgi"]["show-config"] = True
    # self.config_json["uwsgi"]["strict"] = True
    # self.config_json["uwsgi"]["plugin"] = "logfile"
    # if "logfile" in config_json["uwsgi"].get("plugin", ""):
    #    config_json["uwsgi"].pop("plugin")

    def zmq_connect(self):
        pass
        # print(f"Connecting to zmq emperor  {self.conf.EMPEROR_ZMQ_ADDRESS}")
        # self.zmq_socket.connect(f"tcp://{self.conf.EMPEROR_ZMQ_ADDRESS}")

    def start(self):
        pass

    def stop(self):
        pass
        # self.zmq_socket.send_multipart([
        #    b"destroy",
        #    f"{self.service_id}.json".encode(),
        # ])
        # if self.service_config is None:
        #    self.service_config = Path(self.conf.config_dir) / \
        #            f"{self.parent_service_id}" / "apps" \
        #            / f"{self.service_id}.json"

        # if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
        #    shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))


async def get_or_create_project(
    name: str,
    context: dict,
    create_kwargs: dict,
    ) -> Project:

    from pikesquares.service_layer.uow import UnitOfWork

    uow = await services.aget(context, UnitOfWork)
    project = await uow.projects.get_by_name(name)

    if not project:
        project = Project(
            service_id=f"project_{cuid()}",
            name=name,
            **create_kwargs,
        )
        await uow.projects.add(project)
        await uow.commit()
        logger.debug(f"Created {project} ")
    else:
        logger.debug(f"Using existing sandbox project {project}")

    if not await AsyncPath(project.apps_dir).exists():
        await AsyncPath(project.apps_dir).mkdir(parents=True, exist_ok=True)

    uwsgi_config = project.write_uwsgi_config()
    logger.debug(f"wrote config to file: {uwsgi_config}")

    return project

# SandboxProject = NewType("SandboxProject", Project)

"""
def register_project(
    context,
    project_class,
    service_id,
    conf: AppConfig,
    db: TinyDB
    ):
    def project_factory():
        kwargs = {
            "conf": conf,
            "db": db,
            "service_id": service_id,
        }
        return project_class(**kwargs)
    register_factory(context, project_class, project_factory)


def register_sandbox_project(
    context: dict,
    proj_type: SandboxProject,
    proj_class: Project,
    conf: AppConfig,
    db: TinyDB,
    build_config_on_init: bool | None,
    ) -> None:
    def sandbox_project_factory():
        return proj_class(
            conf=conf,
            db=db,
            service_id="project_sandbox",
            build_config_on_init=build_config_on_init,
        )
    register_factory(context, proj_type, sandbox_project_factory)
"""
