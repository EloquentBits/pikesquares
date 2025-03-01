from re import sub

from sqlmodel import (
    SQLModel,
    Field,
    # select,
    # Column,
    # Integer,
    # String,
    # ForeignKey,
    # Relationship,
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

    # id: int | None = Field(sa_column=Column("Id", Integer, primary_key=True, autoincrement=True))
    id: int | None = Field(default=None, primary_key=True)
    service_id: str

    class Config:
        alias_generator = to_camel
        populate_by_name = True
        arbitrary_types_allowed = True

    @property
    def handler_name(self):
        return self.__class__.__name__

    def __repr__(self):
        return f"<{self.handler_name} id={self.id} service_id={self.service_id}>"

    def __str__(self):
        return self.__repr__()
