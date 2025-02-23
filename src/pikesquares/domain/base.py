from re import sub
from typing import Optional, List

from sqlmodel import (
    SQLModel,
    Field,
    Column,
    Integer,
    String,
    ForeignKey,
    Relationship,
)


def to_camel(s: str) -> str:
    """Converts an input string to a camel string.

    Args:
        s (str): Input string.

    Returns:
        str: Camel string.
    """
    ret = sub(r"(_|-)+", " ", s).title().replace(" ", "")
    return "".join([ret[0].lower(), ret[1:]])


class ServiceBase(SQLModel):
    """Base SQL model class.
    """

    id: Optional[int] = Field(sa_column=Column("Id", Integer, primary_key=True, autoincrement=True))

    service_id: str

    class Config:
        alias_generator = to_camel
        populate_by_name = True
        arbitrary_types_allowed = True


"""
class Hero(BaseModel, table=True):
    __tablename__ = "Hero"

    name: str = Field(sa_column=Column("Name", String(30), nullable=False))
    secret_name: str = Field(sa_column=Column("SecretName", String(30), nullable=False))
    age: Optional[int] = Field(sa_column=Column("Age", Integer, nullable=True, default=None))
    team_id: Optional[int] = Field(sa_column=Column("TeamId", Integer, ForeignKey("Team.Id")))

    team: Optional["Team"] = Relationship(back_populates="heroes")


class Team(BaseModel, table=True):
    __tablename__ = "Team"

    name: str = Field(sa_column=Column("Name", String(30), nullable=False, unique=True))

    heroes: List["Hero"] = Relationship(back_populates="team")
"""
