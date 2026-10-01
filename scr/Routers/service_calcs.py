from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_service_calcs
from scr.dbase.database import db_helper
from scr.dbase.schemas.schemas import ServiceCalcResponseSchema, ServiceCalcUpdateSchema

sc_router = APIRouter(prefix="/api/service-calcs", tags=["ServiceCalcs"])


@sc_router.get("/by-request/{request_id}", response_model=ServiceCalcResponseSchema)
async def read_service_calc(
    request_id: int,
    section: str = Query(...),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    item = await crud_service_calcs.get_or_create_service_calc(session, request_id, section)
    await session.commit()
    return item


@sc_router.put("/{calc_id}", response_model=ServiceCalcResponseSchema)
async def update_service_calc(
    calc_id: int,
    data: ServiceCalcUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = calc_id
    result = await crud_service_calcs.update_service_calc(session, data)
    if not result:
        raise HTTPException(status_code=404, detail="Расчёт не найден")
    await session.commit()
    return result
