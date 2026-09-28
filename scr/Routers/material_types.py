from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_material_types
from scr.dbase.database import db_helper
from scr.dbase.schemas.schemas import (
    MaterialTypeCreateSchema,
    MaterialTypeResponseSchema,
    MaterialTypeUpdateSchema,
    PaginatedResponse,
)

mt_router = APIRouter(prefix="/api/material-types", tags=["MaterialTypes"])


@mt_router.post("/", response_model=MaterialTypeResponseSchema)
async def add_type(
    data: MaterialTypeCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new = await crud_material_types.add_type(session=session, in_type=data)
    await session.commit()
    return new


@mt_router.get("/", response_model=PaginatedResponse)
async def read_types(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items, total = await crud_material_types.get_all_types(session=session, search=search, page=page, per_page=per_page)
    return PaginatedResponse(
        items=[MaterialTypeResponseSchema.model_validate(i) for i in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@mt_router.get("/all", response_model=list[MaterialTypeResponseSchema])
async def read_all_types(
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items, _ = await crud_material_types.get_all_types(session=session, per_page=10000)
    return items


@mt_router.get("/{type_id}", response_model=MaterialTypeResponseSchema)
async def read_type(type_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    obj = await crud_material_types.get_type_by_id(session=session, type_id=type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Тип не найден")
    return obj


@mt_router.patch("/", response_model=MaterialTypeResponseSchema)
async def update_type(
    data: MaterialTypeUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_material_types.update_type(session=session, upd_type=data)
    if not result:
        raise HTTPException(status_code=404, detail="Тип не найден")
    await session.commit()
    return result


@mt_router.delete("/{type_id}")
async def delete_type(type_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    result = await crud_material_types.delete_type(session=session, type_id=type_id)
    if not result:
        raise HTTPException(status_code=404, detail="Тип не найден")
    await session.commit()
    return {"message": "Тип удалён"}
