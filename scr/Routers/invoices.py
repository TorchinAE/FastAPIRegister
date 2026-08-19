from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_invoices
from scr.dbase.schemas.schemas import (
    InvoiceCreateSchema,
    InvoiceUpdateSchema,
    InvoiceResponseSchema,
)

inv_router = APIRouter(prefix="/api/invoices", tags=["Invoices"])


@inv_router.get("/by-request/{request_id}", response_model=list[InvoiceResponseSchema])
async def read_invoices(
    request_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    return await crud_invoices.get_invoices_by_request(session, request_id)


@inv_router.post("/", response_model=InvoiceResponseSchema)
async def add_invoice(
    data: InvoiceCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_invoices.add_invoice(session, data)
    await session.commit()
    return result


@inv_router.put("/{inv_id}", response_model=InvoiceResponseSchema)
async def update_invoice(
    inv_id: int,
    data: InvoiceUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = inv_id
    result = await crud_invoices.update_invoice(session, data)
    if not result:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    await session.commit()
    return result


@inv_router.delete("/{inv_id}")
async def delete_invoice(
    inv_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    result = await crud_invoices.delete_invoice(session, inv_id)
    if not result:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    await session.commit()
    return {"message": "Счёт удалён"}
