from sqlalchemy import select, Result, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase.models import Counterparty
from scr.dbase.schemas.schemas import CounterpartyCreateSchema, CounterpartyUpdateSchema


async def get_counterparties(
    session: AsyncSession,
    company_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Counterparty], int]:
    stmt = select(Counterparty).options(selectinload(Counterparty.company)).order_by(Counterparty.id)
    count_stmt = select(func.count(Counterparty.id))

    if company_id:
        stmt = stmt.where(Counterparty.company_id == company_id)
        count_stmt = count_stmt.where(Counterparty.company_id == company_id)
    if search:
        filter_cond = Counterparty.name.ilike(f"%{search}%") | Counterparty.email.ilike(f"%{search}%")
        stmt = stmt.where(filter_cond)
        count_stmt = count_stmt.where(filter_cond)

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_counterparty_by_id(
    session: AsyncSession, cp_id: int
) -> Counterparty | None:
    stmt = select(Counterparty).options(selectinload(Counterparty.company)).where(Counterparty.id == cp_id)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_counterparty_by_email(
    session: AsyncSession, email: str
) -> Counterparty | None:
    stmt = select(Counterparty).where(Counterparty.email == email)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_counterparty(
    session: AsyncSession,
    in_cp: CounterpartyCreateSchema,
    created_by: str | None = None,
) -> Counterparty:
    check_cp = await get_counterparty_by_email(session, in_cp.email)
    if check_cp:
        return check_cp
    cp = Counterparty(**in_cp.model_dump())
    cp.created_by = created_by
    session.add(cp)
    await session.flush()
    return cp


async def update_counterparty(
    session: AsyncSession, upd_cp: CounterpartyUpdateSchema
) -> Counterparty | None:
    check_cp = await get_counterparty_by_id(session, upd_cp.id)
    if not check_cp:
        return None
    for field, value in upd_cp.model_dump(exclude_unset=True).items():
        if field != "id" and hasattr(check_cp, field):
            setattr(check_cp, field, value)
    await session.flush()
    return check_cp


async def delete_counterparty(
    session: AsyncSession, cp_id: int
) -> Counterparty | None:
    cp = await session.get(Counterparty, cp_id)
    if cp:
        await session.delete(cp)
        await session.flush()
    return cp
