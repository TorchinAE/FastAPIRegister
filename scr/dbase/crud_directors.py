from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.models import Directors
from scr.dbase.schemas.schemas import DirectorUpdateSchema, DirectorSchema


async def get_dirs(session: AsyncSession) -> list[Directors]:
    stmt = select(Directors).order_by(Directors.name)
    result: Result = await session.execute(stmt)
    dirs = result.scalars().all()
    return list(dirs)


async def get_dir_to_id(session: AsyncSession, dir_id: int) -> Directors | None:
    return await session.get(Directors, dir_id)


async def get_dir_by_name(session: AsyncSession, name: str) -> Directors | None:
    stmt = select(Directors).where(Directors.name == name)
    result: Result = await session.execute(stmt)
    director = result.scalar_one_or_none()
    return director


async def add_dir(session: AsyncSession, dir_in: DirectorSchema) -> Directors:
    check_dir = await get_dir_by_name(session, dir_in.name)
    if check_dir:
        return check_dir
    new_dir = Directors(**dir_in.model_dump())
    session.add(new_dir)
    await session.flush()
    return new_dir


async def update_dir(
    session: AsyncSession, upd_dir: DirectorUpdateSchema
) -> Directors | None:
    check_dir = await get_dir_to_id(session, upd_dir.id)
    if not check_dir:
        return None
    for field, value in upd_dir.model_dump(exclude_unset=True).items():
        if field != "id" and hasattr(check_dir, field):
            setattr(check_dir, field, value)
    await session.flush()
    return check_dir
