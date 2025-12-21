from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.models import Positions
from scr.dbase.schemas.schemas import PositionCreateSchema


async def get_all_positions(session: AsyncSession) -> list[Positions]:
    stat = select(Positions).order_by(Positions.title)
    result: Result = await session.execute(stat)
    positions = result.scalars().all()
    return list(positions)


async def get_position_id(session: AsyncSession, pos_id: int) -> Positions | None:
    return await session.get(Positions, pos_id)


async def get_position_title(session: AsyncSession, title: str) -> Positions | None:
    stat = select(Positions).where(Positions.title == title)
    result: Result = await session.execute(stat)
    position = result.scalar_one_or_none()
    return position


async def create_position(
    session: AsyncSession, in_position: PositionCreateSchema
) -> Positions:
    check_pos = await get_position_title(session, in_position.title)
    if check_pos:
        return check_pos
    new_pos = Positions(**in_position.model_dump())
    session.add(new_pos)
    await session.flush()
    return new_pos


async def del_position(session: AsyncSession, pos_id: int) -> Positions | None:
    position = await get_position_id(session, pos_id)
    if position:
        await session.delete(position)
        return position
    return None
