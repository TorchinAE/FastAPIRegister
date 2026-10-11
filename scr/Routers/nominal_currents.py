from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_nominal_currents
from scr.dbase.database import db_helper
from scr.dbase.models import Material, Module, NominalCurrent

nc_router = APIRouter(prefix="/api/nominal-currents", tags=["NominalCurrents"])


class NominalCurrentCreateSchema(BaseModel):
    value: int = Field(..., gt=0, le=7000)


@nc_router.get("/")
async def list_nominal_currents(session: AsyncSession = Depends(db_helper.session_dependency)):
    return [{"id": nc.id, "value": nc.value} for nc in await crud_nominal_currents.get_all(session)]


@nc_router.post("/")
async def add_nominal_current(
    data: NominalCurrentCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    obj = await crud_nominal_currents.ensure_value(session, data.value)
    await session.commit()
    return {"id": obj.id, "value": obj.value}


@nc_router.delete("/{nc_id}")
async def delete_nominal_current(nc_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    obj = await session.get(NominalCurrent, nc_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Значение не найдено")
    used = 0
    for model in (Material, Module):
        used += (await session.execute(select(func.count(model.id)).where(model.nom_tok == obj.value))).scalar() or 0
    if used:
        raise HTTPException(status_code=400, detail=f"Значение {obj.value} А используется ({used} шт.)")
    await crud_nominal_currents.delete(session, nc_id)
    await session.commit()
    return {"ok": True}
