from datetime import UTC, datetime

from sqlalchemy import Result, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase.models import InvoiceItem, PayrollItem

# --- Invoice Items (Накладные) ---


async def get_invoice_items(session: AsyncSession, page: int = 1, per_page: int = 20):
    from scr.dbase.models import User

    stmt = select(InvoiceItem).outerjoin(User, InvoiceItem.changed_by_id == User.id).order_by(InvoiceItem.name)
    count_stmt = select(func.count(InvoiceItem.id))

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().unique().all()), total


async def get_all_invoice_items(session: AsyncSession) -> list[InvoiceItem]:
    stmt = select(InvoiceItem).order_by(InvoiceItem.name)
    result: Result = await session.execute(stmt)
    return list(result.scalars().unique().all())


async def get_invoice_item_by_id(session: AsyncSession, item_id: int) -> InvoiceItem | None:
    return await session.get(InvoiceItem, item_id)


async def add_invoice_item(session: AsyncSession, name: str, cost: float, user_id: int | None = None) -> InvoiceItem:
    item = InvoiceItem(
        name=name,
        cost=cost,
        date_modified=datetime.now(UTC),
        changed_by_id=user_id,
    )
    session.add(item)
    await session.flush()
    return item


async def update_invoice_item(
    session: AsyncSession, item_id: int, name: str | None, cost: float | None, user_id: int | None = None
) -> InvoiceItem | None:
    item = await session.get(InvoiceItem, item_id)
    if not item:
        return None
    if name is not None:
        item.name = name
    if cost is not None:
        item.cost = cost
    item.date_modified = datetime.now(UTC)
    item.changed_by_id = user_id
    await session.flush()
    return item


async def delete_invoice_item(session: AsyncSession, item_id: int) -> InvoiceItem | None:
    item = await session.get(InvoiceItem, item_id)
    if item:
        await session.delete(item)
        await session.flush()
    return item


# --- Payroll Items (ФОТ) ---


async def get_payroll_items(session: AsyncSession, page: int = 1, per_page: int = 20):
    stmt = select(PayrollItem).order_by(PayrollItem.name)
    count_stmt = select(func.count(PayrollItem.id))

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().unique().all()), total


async def get_all_payroll_items(session: AsyncSession) -> list[PayrollItem]:
    stmt = select(PayrollItem).order_by(PayrollItem.name)
    result: Result = await session.execute(stmt)
    return list(result.scalars().unique().all())


async def get_payroll_item_by_id(session: AsyncSession, item_id: int) -> PayrollItem | None:
    return await session.get(PayrollItem, item_id)


async def add_payroll_item(session: AsyncSession, name: str, cost: float, user_id: int | None = None) -> PayrollItem:
    item = PayrollItem(
        name=name,
        cost=cost,
        date_modified=datetime.now(UTC),
        changed_by_id=user_id,
    )
    session.add(item)
    await session.flush()
    return item


async def update_payroll_item(
    session: AsyncSession, item_id: int, name: str | None, cost: float | None, user_id: int | None = None
) -> PayrollItem | None:
    item = await session.get(PayrollItem, item_id)
    if not item:
        return None
    if name is not None:
        item.name = name
    if cost is not None:
        item.cost = cost
    item.date_modified = datetime.now(UTC)
    item.changed_by_id = user_id
    await session.flush()
    return item


async def delete_payroll_item(session: AsyncSession, item_id: int) -> PayrollItem | None:
    item = await session.get(PayrollItem, item_id)
    if item:
        await session.delete(item)
        await session.flush()
    return item
