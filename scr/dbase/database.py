from scr.dbase.models import Base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from scr.config import settings


engine = create_async_engine(
    url=settings.database_url,
    echo=True,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.connect() as conn:
        await conn.run_sync(Base.metadata.create_all)
