from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.constants import PAYMENT_TYPES
from scr.dbase.models import PaymentItem, Request
from scr.dbase.schemas.schemas import PaymentItemUpdateSchema


async def get_payment_items_by_request(session: AsyncSession, request_id: int) -> list[PaymentItem]:
    stmt = select(PaymentItem).where(PaymentItem.request_id == request_id).order_by(PaymentItem.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def ensure_payment_items(session: AsyncSession, request_id: int) -> list[PaymentItem]:
    existing = await get_payment_items_by_request(session, request_id)
    existing_types = {p.payment_type for p in existing}
    for pt in PAYMENT_TYPES:
        if pt not in existing_types:
            session.add(PaymentItem(request_id=request_id, payment_type=pt))
    await session.flush()
    return await get_payment_items_by_request(session, request_id)


async def update_payment_item(session: AsyncSession, data: PaymentItemUpdateSchema) -> PaymentItem | None:
    item = await session.get(PaymentItem, data.id)
    if not item:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field != "id" and hasattr(item, field):
            setattr(item, field, value)
    await session.flush()
    return item


async def get_requests_with_payments(session: AsyncSession, request_ids: list[int]) -> list[Request]:
    """ТКП с порядком оплаты в порядке переданных id."""
    if not request_ids:
        return []
    stmt = (
        select(Request)
        .where(Request.id.in_(request_ids))
        .options(selectinload(Request.company), selectinload(Request.payment_items))
    )
    by_id = {r.id: r for r in (await session.execute(stmt)).scalars().all()}
    return [by_id[rid] for rid in dict.fromkeys(request_ids) if rid in by_id]


def sorted_payment_items(items: list[PaymentItem]) -> list[PaymentItem]:
    """Строки порядка оплаты в порядке видов платежей (предоплата, доплаты, отсрочка)."""
    order = {pt: i for i, pt in enumerate(PAYMENT_TYPES)}
    return sorted(items, key=lambda pi: (order.get(pi.payment_type, len(order)), pi.id))
