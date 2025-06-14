import uuid
from typing import NewType

import structlog
from pluggy import HookimplMarker, HookspecMarker, PluginManager
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlmodel import Field, Relationship

from pikesquares.domain.base import TimeStampedBase

logger = structlog.getLogger()

AppRuntimePluginManager = NewType("AppRuntimePluginManager", PluginManager)
hook_spec = HookspecMarker("app-runtime" )
hook_impl = HookimplMarker("app-runtime" )


class AppRuntimeHookSpec:
    """
    App Runtime Hook Specification
    """

    @hook_spec
    def prompt_for_version(self) -> str:
        ...

class AppRuntime(AsyncAttrs, TimeStampedBase):
    """Base App Runtime SQL model class."""

    __tablename__ = "app_runtimes"

    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4()),
        max_length=36,
    )
    version: str = Field(max_length=25)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class AppCodebase(AsyncAttrs, TimeStampedBase, table=True):

    __tablename__ = "app_codebases"

    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4()),
        max_length=36,
    )
    root_dir: str = Field(max_length=255)
    repo_dir: str = Field(max_length=255)
    repo_git_url: str = Field(max_length=255)
    venv_dir: str = Field(max_length=255)
    editable_mode: bool = Field(default=False)

    wsgi_apps: list["WsgiApp"] = Relationship(back_populates="app_codebase")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

