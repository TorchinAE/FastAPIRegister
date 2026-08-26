from sqlalchemy import select, Result, func
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import Positions
from scr.dbase.schemas.schemas import PositionCreateSchema, PositionUpdateSchema


async def get_all_positions(
    session: AsyncSession, search: str | None = None, page: int = 1, per_page: int = 20
) -> tuple[list[Positions], int]:
    stmt = select(Positions).order_by(Positions.name)
    count_stmt = select(func.count(Positions.id))

    if search:
        stmt = stmt.where(Positions.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(Positions.name.ilike(f"%{search}%"))

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_position_id(session: AsyncSession, pos_id: int) -> Positions | None:
    return await session.get(Positions, pos_id)


async def get_position_name(session: AsyncSession, name: str) -> Positions | None:
    stmt = select(Positions).where(Positions.name == name)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_position(
    session: AsyncSession, in_position: PositionCreateSchema, created_by: str | None = None
) -> Positions:
    check_pos = await get_position_name(session, in_position.name)
    if check_pos:
        return check_pos
    new_pos = Positions(**in_position.model_dump())
    new_pos.created_by = created_by
    session.add(new_pos)
    await session.flush()
    return new_pos


async def update_position(
    session: AsyncSession, upd_position: PositionUpdateSchema
) -> Positions | None:
    check_position = await get_position_id(session, upd_position.id)
    if not check_position:
        return None
    for pos_field, value in upd_position.model_dump(exclude_unset=True).items():
        if pos_field != "id" and hasattr(check_position, pos_field):
            setattr(check_position, pos_field, value)
    await session.flush()
    return check_position


async def delete_position(session: AsyncSession, pos_id: int) -> Positions | None:
    position = await get_position_id(session, pos_id)
    if position:
        await session.delete(position)
        return position
    return None
