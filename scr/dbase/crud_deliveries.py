from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import Delivery
from scr.dbase.schemas.schemas import DeliveryCreateSchema, DeliveryUpdateSchema


async def get_delivery_by_request(session: AsyncSession, request_id: int) -> Delivery | None:
    stmt = select(Delivery).where(Delivery.request_id == request_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_delivery(session: AsyncSession, request_id: int) -> Delivery:
    delivery = await get_delivery_by_request(session, request_id)
    if not delivery:
        delivery = Delivery(request_id=request_id)
        session.add(delivery)
        await session.flush()
    return delivery


async def update_delivery(session: AsyncSession, data: DeliveryUpdateSchema) -> Delivery | None:
    item = await session.get(Delivery, data.id)
    if not item:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field != "id" and hasattr(item, field):
            setattr(item, field, value)
    await session.flush()
    return item
