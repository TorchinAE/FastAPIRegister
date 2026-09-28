from sqlalchemy import Result, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import MaterialType
from scr.dbase.schemas.schemas import MaterialTypeCreateSchema, MaterialTypeUpdateSchema


async def get_all_types(
    session: AsyncSession, search: str | None = None, page: int = 1, per_page: int = 20
) -> tuple[list[MaterialType], int]:
    stmt = select(MaterialType).order_by(MaterialType.name)
    count_stmt = select(func.count(MaterialType.id))

    if search:
        stmt = stmt.where(MaterialType.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(MaterialType.name.ilike(f"%{search}%"))

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_type_by_id(session: AsyncSession, type_id: int) -> MaterialType | None:
    return await session.get(MaterialType, type_id)


async def get_type_by_name(session: AsyncSession, name: str) -> MaterialType | None:
    stmt = select(MaterialType).where(MaterialType.name == name)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_type(
    session: AsyncSession, in_type: MaterialTypeCreateSchema, created_by: str | None = None
) -> MaterialType:
    check = await get_type_by_name(session, in_type.name)
    if check:
        return check
    new_type = MaterialType(**in_type.model_dump())
    new_type.created_by = created_by
    session.add(new_type)
    await session.flush()
    return new_type


async def update_type(session: AsyncSession, upd_type: MaterialTypeUpdateSchema) -> MaterialType | None:
    check = await get_type_by_id(session, upd_type.id)
    if not check:
        return None
    for field, value in upd_type.model_dump(exclude_unset=True).items():
        if field != "id" and hasattr(check, field):
            setattr(check, field, value)
    await session.flush()
    return check


async def delete_type(session: AsyncSession, type_id: int) -> MaterialType | None:
    obj = await get_type_by_id(session, type_id)
    if obj:
        await session.delete(obj)
        await session.flush()
    return obj
