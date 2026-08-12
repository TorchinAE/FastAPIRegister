from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_counterparties
from scr.dbase.schemas.schemas import (
    CounterpartyCreateSchema,
    CounterpartyUpdateSchema,
    CounterpartyResponseSchema,
    PaginatedResponse,
)

cp_router = APIRouter(prefix="/api/counterparties", tags=["Counterparties"])


@cp_router.post("/", response_model=CounterpartyResponseSchema)
async def add_counterparty(
    counterparty: CounterpartyCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new_cp = await crud_counterparties.add_counterparty(
        session=session, in_cp=counterparty
    )
    await session.commit()
    return new_cp


def _cp_response(cp) -> CounterpartyResponseSchema:
    return CounterpartyResponseSchema(
        id=cp.id,
        name=cp.name,
        email=cp.email,
        phone=cp.phone,
        company_id=cp.company_id,
        company_name=cp.company.name if cp.company else None,
        created_by=cp.created_by,
    )


@cp_router.get("/", response_model=PaginatedResponse)
async def read_counterparties(
    company_id: int | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    cps, total = await crud_counterparties.get_counterparties(
        session=session, company_id=company_id, search=search, page=page, per_page=per_page
    )
    return PaginatedResponse(
        items=[_cp_response(c) for c in cps],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@cp_router.get("/{cp_id}", response_model=CounterpartyResponseSchema)
async def read_counterparty(
    cp_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    cp = await crud_counterparties.get_counterparty_by_id(session=session, cp_id=cp_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Контрагент не найден")
    return _cp_response(cp)


@cp_router.patch("/", response_model=CounterpartyResponseSchema)
async def update_counterparty(
    data: CounterpartyUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_counterparties.update_counterparty(session=session, upd_cp=data)
    if not result:
        raise HTTPException(status_code=404, detail="Контрагент не найден")
    await session.commit()
    return result


@cp_router.delete("/{cp_id}")
async def delete_counterparty(
    cp_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    result = await crud_counterparties.delete_counterparty(session=session, cp_id=cp_id)
    if not result:
        raise HTTPException(status_code=404, detail="Контрагент не найден")
    await session.commit()
    return {"message": "Контрагент удален"}
