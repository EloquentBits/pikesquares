from re import sub

from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlmodel import (
    SQLModel,
    Field,
    select,
    Column,
    Integer,
    # String,
    # ForeignKey,
    # Relationship,
)

from sqlalchemy.ext.asyncio import AsyncSession


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

    @classmethod
    async def create(
            cls,
            db: AsyncSession,
            # id=None,
            **kwargs
        ):
        # if not id:
        #    id = uuid4().hex

        transaction = cls(
            #id=id,
            **kwargs
        )
        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)
        return transaction

    @classmethod
    async def get(cls, db: AsyncSession, id: str):
        try:
            transaction = await db.get(cls, id)
        except NoResultFound:
            return None
        return transaction

    @classmethod
    async def get_all(cls, db: AsyncSession):
        return (await db.execute(select(cls))).scalars().all()



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
