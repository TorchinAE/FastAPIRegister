from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase.models import Invoice, Request
from scr.dbase.schemas.schemas import InvoiceCreateSchema, InvoiceUpdateSchema


async def get_invoices_by_request(
    session: AsyncSession, request_id: int
) -> list[Invoice]:
    stmt = (
        select(Invoice)
        .where(Invoice.request_id == request_id)
        .order_by(Invoice.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_invoice_by_id(
    session: AsyncSession, invoice_id: int
) -> Invoice | None:
    return await session.get(Invoice, invoice_id)


async def add_invoice(
    session: AsyncSession,
    data: InvoiceCreateSchema,
    created_by: str | None = None,
) -> Invoice:
    invoice = Invoice(
        request_id=data.request_id,
        invoice_num=data.invoice_num,
        invoice_date=data.invoice_date,
        percent=data.percent,
        amount=data.amount,
        created_by=created_by,
    )
    session.add(invoice)
    await session.flush()
    return invoice


async def update_invoice(
    session: AsyncSession, data: InvoiceUpdateSchema
) -> Invoice | None:
    invoice = await session.get(Invoice, data.id)
    if not invoice:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field != "id" and hasattr(invoice, field):
            setattr(invoice, field, value)
    await session.flush()
    return invoice


async def delete_invoice(session: AsyncSession, invoice_id: int) -> Invoice | None:
    invoice = await session.get(Invoice, invoice_id)
    if invoice:
        await session.delete(invoice)
        await session.flush()
    return invoice
