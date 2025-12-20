from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from scr.dbase.models import Base
from config import settings

engine = create_async_engine(url=settings.database_url, echo=True)

async_session = async_sessionmaker(engine, expire_on_commit=False)
