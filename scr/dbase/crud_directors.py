from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.models import Directors
from scr.dbase.schemas.schemas import DirectorSchema


async def get_dirs(session: AsyncSession) -> list[Directors]:
    stmt = select(Directors).order_by(Directors.name)
    result: Result = await session.execute(stmt)
    dirs = result.scalars().all()
    return list(dirs)


async def get_dir_to_id(session: AsyncSession, dir_id: int) -> Directors | None:
    return await session.get(Directors, dir_id)


async def get_dir_by_name(session: AsyncSession, name: str) -> Directors | None:
    stat = select(Directors).where(Directors.name == name)
    result: Result = await session.execute(stat)
    director = result.scalar_one_or_none()
    return director


async def create_dir(session: AsyncSession, dir_in: DirectorSchema) -> Directors:
    check_dir = await get_dir_by_name(session, dir_in.name)
    if check_dir:
        return check_dir
    new_dir = Directors(**dir_in.model_dump())
    session.add(new_dir)
    await session.commit()
    return new_dir
