import json
# import shutil
from pathlib import Path
from typing import NewType

# import zmq
from tinydb import Query, TinyDB
import pydantic
# from uwsgiconf import uwsgi

from pikesquares import conf
from pikesquares.services.base import BaseService
from pikesquares.services import register_factory
from pikesquares.presets import Section
from ..presets.project import ProjectSection

__all__ = (
    "Project",
)


class Project(BaseService):
    config_section_class: Section = ProjectSection
    tiny_db_table: str = "projects"

    @pydantic.computed_field
    def service_config(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / "projects" / f"{self.service_id}.json"

    @pydantic.computed_field
    def touch_reload_file(self) -> Path:
        return Path(self.conf.CONFIG_DIR) / "projects" / f"{self.service_id}.json"

    @pydantic.computed_field
    def apps_dir(self) -> str:
        apps_dir = Path(self.conf.CONFIG_DIR) / f"{self.service_id}" / "apps"
        if apps_dir and not apps_dir.exists():
            apps_dir.mkdir(parents=True, exist_ok=True)
        return str(apps_dir.resolve())

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
        #    self.service_config = Path(self.conf.CONFIG_DIR) / \
        #            f"{self.parent_service_id}" / "apps" \
        #            / f"{self.service_id}.json"

        # if self.is_started() and not str(self.service_config.resolve()).endswith(".stopped"):
        #    shutil.move(self.service_config, self.service_config.with_suffix(".stopped"))


# def get_project(conf: ClientConfig, project_id):
#    with TinyDB(f"{Path(conf.DATA_DIR) / 'device-db.json'}") as db:
#        return db.table('projects').\
#            get(Query().service_id == project_id)


SandboxProject = NewType("SandboxProject", Project)


def register_project(context, project_class, service_id, client_conf: conf.ClientConfig, db: TinyDB):
    def project_factory():
        kwargs = {
            "conf": client_conf,
            "db": db,
            "service_id": service_id,
        }
        return project_class(**kwargs)
    register_factory(context, project_class, project_factory)


def register_sandbox_project(
    context: dict,
    proj_type: SandboxProject,
    proj_class: Project,
    client_conf: conf.ClientConfig,
    db: TinyDB,
    flush_config_on_init: bool | None,
    ) -> None:
    def sandbox_project_factory():
        return proj_class(
            conf=client_conf,
            db=db,
            service_id="project_sandbox",
            flush_config_on_init=flush_config_on_init,
        )
    register_factory(context, proj_type, sandbox_project_factory)
