from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_deliveries
from scr.dbase.database import db_helper
from scr.dbase.schemas.schemas import DeliveryCreateSchema, DeliveryResponseSchema, DeliveryUpdateSchema

del_router = APIRouter(prefix="/api/deliveries", tags=["Deliveries"])


@del_router.get("/by-request/{request_id}", response_model=DeliveryResponseSchema)
async def read_delivery(request_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    delivery = await crud_deliveries.get_or_create_delivery(session, request_id)
    await session.commit()
    return delivery


@del_router.put("/{delivery_id}", response_model=DeliveryResponseSchema)
async def update_delivery(
    delivery_id: int,
    data: DeliveryUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = delivery_id
    result = await crud_deliveries.update_delivery(session, data)
    if not result:
        raise HTTPException(status_code=404, detail="Доставка не найдена")
    await session.commit()
    return result
