import uuid

from sqlmodel import Field

from pikesquares.domain.base import TimeStampedBase


class BaseAppCodebase(TimeStampedBase):
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

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
