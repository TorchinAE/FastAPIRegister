from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_accuracy_classes
from scr.dbase.database import db_helper
from scr.dbase.models import AccuracyClass, Material

ac_router = APIRouter(prefix="/api/accuracy-classes", tags=["AccuracyClasses"])


class AccuracyClassCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)


@ac_router.get("/")
async def list_accuracy_classes(session: AsyncSession = Depends(db_helper.session_dependency)):
    return [{"id": c.id, "name": c.name} for c in await crud_accuracy_classes.get_all(session)]


@ac_router.post("/")
async def add_accuracy_class(
    data: AccuracyClassCreateSchema, session: AsyncSession = Depends(db_helper.session_dependency)
):
    obj = await crud_accuracy_classes.ensure_name(session, data.name)
    if not obj:
        raise HTTPException(status_code=400, detail="Пустое название")
    await session.commit()
    return {"id": obj.id, "name": obj.name}


@ac_router.delete("/{class_id}")
async def delete_accuracy_class(class_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    obj = await session.get(AccuracyClass, class_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Класс точности не найден")
    stmt = select(func.count(Material.id)).where(Material.accuracy_class == obj.name)
    used = (await session.execute(stmt)).scalar() or 0
    if used:
        raise HTTPException(status_code=400, detail=f"«{obj.name}» используется в материалах ({used} шт.)")
    await crud_accuracy_classes.delete(session, class_id)
    await session.commit()
    return {"ok": True}
