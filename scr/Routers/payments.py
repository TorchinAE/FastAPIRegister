from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_payments
from scr.dbase.schemas.schemas import (
    PaymentItemUpdateSchema,
    PaymentItemResponseSchema,
)

pay_router = APIRouter(prefix="/api/payments", tags=["Payments"])


@pay_router.get("/by-request/{request_id}", response_model=list[PaymentItemResponseSchema])
async def read_payments(
    request_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    return await crud_payments.ensure_payment_items(session, request_id)


@pay_router.put("/{item_id}", response_model=PaymentItemResponseSchema)
async def update_payment(
    item_id: int,
    data: PaymentItemUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = item_id
    result = await crud_payments.update_payment_item(session, data)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Платёж не найден")
    await session.commit()
    return result
