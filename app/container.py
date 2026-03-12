from dataclasses import dataclass

import aiosqlite

from db.connection import open_db


@dataclass
class Container:
    db: aiosqlite.Connection | None = None


container = Container()


async def init_container() -> None:
    if container.db is None:
        container.db = await open_db()


async def close_container() -> None:
    if container.db is not None:
        await container.db.close()
        container.db = None
