from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_requests
from scr.dbase.models import RequestStatus
from scr.dbase.schemas.schemas import (
    RequestCreateSchema,
    RequestUpdateSchema,
    RequestResponseSchema,
    PaginatedResponse,
)

req_router = APIRouter(prefix="/api/requests", tags=["Requests"])


@req_router.post("/", response_model=RequestResponseSchema)
async def add_request(
    request: RequestCreateSchema,
    manager_id: int = Query(..., description="ID менеджера из сессии"),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new_req = await crud_requests.add_request(
        session=session, in_req=request, manager_id=manager_id
    )
    if not new_req:
        raise HTTPException(status_code=400, detail="Контрагент не найден")
    await session.commit()
    return new_req


@req_router.get("/", response_model=PaginatedResponse)
async def read_requests(
    status: RequestStatus | None = Query(None),
    counterparty_id: int | None = Query(None),
    company_id: int | None = Query(None),
    manager_id: int | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    requests, total = await crud_requests.get_requests(
        session=session,
        status=status,
        counterparty_id=counterparty_id,
        company_id=company_id,
        manager_id=manager_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
    )
    return PaginatedResponse(
        items=[RequestResponseSchema.model_validate(r) for r in requests],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@req_router.get("/{req_id}", response_model=RequestResponseSchema)
async def read_request(
    req_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    req = await crud_requests.get_request_by_id(session=session, req_id=req_id)
    if not req:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    return req


@req_router.put("/{req_id}", response_model=RequestResponseSchema)
async def update_request(
    req_id: int,
    data: RequestUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = req_id
    result = await crud_requests.update_request(session=session, upd_req=data)
    if not result:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    await session.commit()
    return result


@req_router.delete("/{req_id}")
async def delete_request(
    req_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    result = await crud_requests.delete_request(session=session, req_id=req_id)
    if not result:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    await session.commit()
    return {"message": "Запрос удален"}
