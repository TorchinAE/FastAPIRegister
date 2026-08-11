from sqlalchemy import select, Result, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from scr.dbase.models import Directors
from scr.dbase.schemas.schemas import DirectorUpdateSchema, DirectorSchema


async def get_dirs(
    session: AsyncSession,
    position_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Directors], int]:
    stmt = select(Directors).options(selectinload(Directors.position)).order_by(Directors.name)
    count_stmt = select(func.count(Directors.id))

    if position_id:
        stmt = stmt.where(Directors.position_id == position_id)
        count_stmt = count_stmt.where(Directors.position_id == position_id)
    if search:
        stmt = stmt.where(Directors.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(Directors.name.ilike(f"%{search}%"))

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_dir_to_id(session: AsyncSession, dir_id: int) -> Directors | None:
    stmt = select(Directors).options(selectinload(Directors.position)).where(Directors.id == dir_id)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_dir_by_name(session: AsyncSession, name: str) -> Directors | None:
    stmt = select(Directors).where(Directors.name == name)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_dir(
    session: AsyncSession, dir_in: DirectorSchema, created_by: str | None = None
) -> Directors:
    check_dir = await get_dir_by_name(session, dir_in.name)
    if check_dir:
        return check_dir
    new_dir = Directors(**dir_in.model_dump())
    new_dir.created_by = created_by
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


async def delete_dir(session: AsyncSession, dir_id: int) -> Directors | None:
    director = await session.get(Directors, dir_id)
    if director:
        await session.delete(director)
        await session.flush()
    return director
