from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_units
from scr.dbase.database import db_helper
from scr.dbase.models import DEFAULT_UNIT, Material, Unit

units_router = APIRouter(prefix="/api/units", tags=["Units"])


class UnitCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)


@units_router.get("/")
async def list_units(session: AsyncSession = Depends(db_helper.session_dependency)):
    return [{"id": u.id, "name": u.name} for u in await crud_units.get_all(session)]


@units_router.post("/")
async def add_unit(data: UnitCreateSchema, session: AsyncSession = Depends(db_helper.session_dependency)):
    obj = await crud_units.ensure_name(session, data.name)
    if not obj:
        raise HTTPException(status_code=400, detail="Пустое название")
    await session.commit()
    return {"id": obj.id, "name": obj.name}


@units_router.delete("/{unit_id}")
async def delete_unit(unit_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    obj = await session.get(Unit, unit_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Единица не найдена")
    if obj.name == DEFAULT_UNIT:
        raise HTTPException(status_code=400, detail=f"«{DEFAULT_UNIT}» — единица по умолчанию, удалить нельзя")
    used = (await session.execute(select(func.count(Material.id)).where(Material.unit == obj.name))).scalar() or 0
    if used:
        raise HTTPException(status_code=400, detail=f"«{obj.name}» используется в материалах ({used} шт.)")
    await crud_units.delete(session, unit_id)
    await session.commit()
    return {"ok": True}
