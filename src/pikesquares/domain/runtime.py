import uuid

import structlog
from sqlmodel import Field

from pikesquares.domain.base import TimeStampedBase

logger = structlog.getLogger()


class AppRuntime(TimeStampedBase):
    """Base App Runtime SQL model class."""

    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4()),
        max_length=36,
    )
    version: str = Field(max_length=25)
    lang: str = Field(max_length=25)
    implementation: str = Field(max_length=25)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
