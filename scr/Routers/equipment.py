from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_equipment
from scr.dbase.schemas.schemas import (
    EquipmentCreateSchema,
    EquipmentUpdateSchema,
    EquipmentResponseSchema,
    CompositionItemSchema,
    CompositionResponseSchema,
    PaginatedResponse,
)

eq_router = APIRouter(prefix="/api/equipment", tags=["Equipment"])


@eq_router.post("/", response_model=EquipmentResponseSchema)
async def add_equipment(
    data: EquipmentCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new_eq = await crud_equipment.add_equipment(session=session, in_eq=data)
    await session.commit()
    return new_eq


@eq_router.get("/", response_model=PaginatedResponse)
async def read_equipment(
    search: str | None = Query(None),
    section_id: int | None = Query(None),
    is_composite: bool | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items, total = await crud_equipment.get_equipment_list(
        session=session, search=search, section_id=section_id,
        is_composite=is_composite, page=page, per_page=per_page
    )
    return PaginatedResponse(
        items=[EquipmentResponseSchema.model_validate(i) for i in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@eq_router.get("/{eq_id}", response_model=EquipmentResponseSchema)
async def read_equipment_item(
    eq_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    eq = await crud_equipment.get_equipment_by_id(session=session, eq_id=eq_id)
    if not eq:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")
    return eq


@eq_router.patch("/", response_model=EquipmentResponseSchema)
async def update_equipment(
    data: EquipmentUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_equipment.update_equipment(session=session, upd_eq=data)
    if not result:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")
    await session.commit()
    return result


@eq_router.delete("/{eq_id}")
async def delete_equipment(
    eq_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    result = await crud_equipment.delete_equipment(session=session, eq_id=eq_id)
    if not result:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")
    await session.commit()
    return {"message": "Оборудование удалено"}


@eq_router.get("/{eq_id}/composition", response_model=list[CompositionResponseSchema])
async def get_composition(
    eq_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    comps = await crud_equipment.get_composition(session, eq_id)
    return [CompositionResponseSchema(
        id=c.id, parent_id=c.parent_id, child_id=c.child_id,
        quantity=c.quantity, child_name=c.child.name if c.child else None
    ) for c in comps]


@eq_router.put("/{eq_id}/composition")
async def set_composition(
    eq_id: int, components: list[CompositionItemSchema],
    session: AsyncSession = Depends(db_helper.session_dependency)
):
    result = await crud_equipment.set_composition(
        session, eq_id, [c.model_dump() for c in components]
    )
    if not result:
        raise HTTPException(status_code=404, detail="Оборудование не найдено")
    await session.commit()
    return {"ok": True}
