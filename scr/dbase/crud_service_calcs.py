from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import ServiceCalc
from scr.dbase.schemas.schemas import ServiceCalcUpdateSchema


async def get_or_create_service_calc(session: AsyncSession, request_id: int, section: str) -> ServiceCalc:
    stmt = select(ServiceCalc).where(ServiceCalc.request_id == request_id, ServiceCalc.section == section)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        item = ServiceCalc(request_id=request_id, section=section)
        session.add(item)
        await session.flush()
    return item


async def update_service_calc(session: AsyncSession, data: ServiceCalcUpdateSchema) -> ServiceCalc | None:
    item = await session.get(ServiceCalc, data.id)
    if not item:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        if field != "id" and hasattr(item, field):
            setattr(item, field, value)
    await session.flush()
    return item
