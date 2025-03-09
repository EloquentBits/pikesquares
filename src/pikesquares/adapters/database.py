import logging
from typing import Any

import contextlib
from typing import AsyncIterator

from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    async_sessionmaker,
    create_async_engine,
)
# from sqlalchemy.orm import sessionmaker

from pikesquares.app.core.config import settings


logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


class DatabaseSessionManager:
    def __init__(self, host: str, engine_kwargs: dict[str, Any] = {}):
        connect_args = {"check_same_thread": False}
        self._engine = create_async_engine(
            host, connect_args=connect_args, **engine_kwargs
        )
        self._sessionmaker = async_sessionmaker(
            autocommit=False,
            bind=self._engine,
            expire_on_commit=False,
            class_=SQLModelAsyncSession,
        )

    async def close(self):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        await self._engine.dispose()

        self._engine = None
        self._sessionmaker = None

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[SQLModelAsyncSession]:
        if self._sessionmaker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    # Used for testing
    # async def create_all(self, connection: AsyncConnection):
    #    await connection.run_sync(Base.metadata.create_all)

    # async def drop_all(self, connection: AsyncConnection):
    #    await connection.run_sync(Base.metadata.drop_all)


sessionmanager = DatabaseSessionManager(
    settings.SQLALCHEMY_DATABASE_URI, {"echo": True}
)


async def get_session() -> SQLModelAsyncSession:
    async with sessionmanager.session() as session:
        return session


# async def initialize_database(engine):
#    async with engine.begin() as conn:
#        await conn.run_sync(
#            lambda conn: SQLModel.metadata.create_all(conn)
#        )

# engine = create_async_engine(
#    settings.SQLALCHEMY_DATABASE_URI,
#    echo=True,
#    future=True,
#    pool_size=20,
#    max_overflow=20,
#    pool_recycle=3600,
# )
#

# @contextlib.asynccontextmanager
# async def get_session() -> SQLModelAsyncSession:
#     async_session = sessionmaker(engine, class_=SQLModelAsyncSession, expire_on_commit=False)
#     async with async_session() as session:
#         yield session
