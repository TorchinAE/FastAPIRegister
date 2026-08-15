from datetime import datetime

from sqlalchemy import select, Result, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase.models import Request, RequestStatus, Counterparty
from scr.dbase.schemas.schemas import RequestCreateSchema, RequestUpdateSchema


async def get_requests(
    session: AsyncSession,
    status: RequestStatus | None = None,
    counterparty_id: int | None = None,
    company_id: int | None = None,
    manager_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Request], int]:
    stmt = select(Request).options(
        selectinload(Request.equipment),
        selectinload(Request.manager),
        selectinload(Request.company),
    ).order_by(Request.id.desc())
    count_stmt = select(func.count(Request.id))

    if status:
        stmt = stmt.where(Request.status == status)
        count_stmt = count_stmt.where(Request.status == status)
    if counterparty_id:
        stmt = stmt.where(Request.counterparty_id == counterparty_id)
        count_stmt = count_stmt.where(Request.counterparty_id == counterparty_id)
    if company_id:
        stmt = stmt.where(Request.company_id == company_id)
        count_stmt = count_stmt.where(Request.company_id == company_id)
    if manager_id:
        stmt = stmt.where(Request.manager_id == manager_id)
        count_stmt = count_stmt.where(Request.manager_id == manager_id)
    if date_from:
        stmt = stmt.where(Request.request_date >= date_from)
        count_stmt = count_stmt.where(Request.request_date >= date_from)
    if date_to:
        stmt = stmt.where(Request.request_date <= date_to)
        count_stmt = count_stmt.where(Request.request_date <= date_to)

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_request_by_id(
    session: AsyncSession, req_id: int
) -> Request | None:
    stmt = select(Request).options(
        selectinload(Request.counterparty),
        selectinload(Request.company),
        selectinload(Request.manager),
        selectinload(Request.equipment),
    ).where(Request.id == req_id)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_request(
    session: AsyncSession,
    in_req: RequestCreateSchema,
    manager_id: int,
    created_by: str | None = None,
    user_city: str = "ив",
) -> Request:
    counterparty = await session.get(Counterparty, in_req.counterparty_id)
    if not counterparty:
        return None

    req = Request(
        counterparty_id=in_req.counterparty_id,
        company_id=counterparty.company_id,
        manager_id=manager_id,
        equipment_id=in_req.equipment_id,
        description=in_req.description,
        notes=in_req.notes,
        status=in_req.status,
        cost=in_req.cost,
        issue_date=in_req.issue_date,
        created_by=created_by,
        bktpb=in_req.bktpb,
        ktpb=in_req.ktpb,
        ktp=in_req.ktp,
        kso_393=in_req.kso_393,
        kso_204=in_req.kso_204,
        k_104=in_req.k_104,
        k_104m=in_req.k_104m,
        sho=in_req.sho,
        pku=in_req.pku,
        pus=in_req.pus,
        parn=in_req.parn,
    )
    session.add(req)
    await session.flush()

    req.tkp_num = f"{req.id}-{user_city}"
    await session.flush()

    return req


async def update_request(
    session: AsyncSession, upd_req: RequestUpdateSchema
) -> Request | None:
    check_req = await get_request_by_id(session, upd_req.id)
    if not check_req:
        return None

    update_data = upd_req.model_dump(exclude_unset=True)
    # If counterparty changed, auto-update company_id
    if "counterparty_id" in update_data:
        counterparty = await session.get(Counterparty, update_data["counterparty_id"])
        if counterparty:
            check_req.company_id = counterparty.company_id

    for field, value in update_data.items():
        if field not in ("id", "created_by", "created_at", "tkp_num") and hasattr(check_req, field):
            setattr(check_req, field, value)

    await session.flush()
    return check_req


async def delete_request(session: AsyncSession, req_id: int) -> Request | None:
    req = await session.get(Request, req_id)
    if req:
        await session.delete(req)
        await session.flush()
    return req
