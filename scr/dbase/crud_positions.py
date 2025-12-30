from black.cache import field
from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.horizontal_shard import set_shard_id

from scr.dbase.models import Positions
from scr.dbase.schemas.schemas import PositionCreateSchema, PositionUpdateSchema


async def get_all_positions(session: AsyncSession) -> list[Positions]:
    stmt = select(Positions).order_by(Positions.title)
    result: Result = await session.execute(stmt)
    positions = result.scalars().all()
    return list(positions)


async def get_position_id(session: AsyncSession, pos_id: int) -> Positions | None:
    return await session.get(Positions, pos_id)


async def get_position_title(session: AsyncSession, title: str) -> Positions | None:
    stmt = select(Positions).where(Positions.title == title)
    result: Result = await session.execute(stmt)
    position = result.scalar_one_or_none()
    return position


async def add_position(
    session: AsyncSession, in_position: PositionCreateSchema
) -> Positions:
    check_pos = await get_position_title(session, in_position.title)
    if check_pos:
        return check_pos
    new_pos = Positions(**in_position.model_dump())
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
        if field != "id" and hasattr(upd_position, pos_field):
            setattr(upd_position, pos_field, value)
    await session.flush()
    return check_position


async def delete_position(session: AsyncSession, pos_id: int) -> Positions | None:
    position = await get_position_id(session, pos_id)
    if position:
        await session.delete(position)
        return position
    return None
