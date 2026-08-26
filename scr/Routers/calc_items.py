from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_calc_items
from scr.dbase.schemas.schemas import (
    CalcItemCreateSchema, CalcItemUpdateSchema, CalcItemResponseSchema,
)

ci_router = APIRouter(prefix="/api/calc-items", tags=["Calc Items"])


@ci_router.get("/{request_id}/{calc_type}", response_model=list[CalcItemResponseSchema])
async def list_calc_items(
    request_id: int, calc_type: str,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items = await crud_calc_items.get_calc_items(session, request_id, calc_type)
    result = []
    for item in items:
        result.append(CalcItemResponseSchema(
            id=item.id,
            request_id=item.request_id,
            calc_type=item.calc_type,
            equipment_id=item.equipment_id,
            equipment_name=item.equipment.name if item.equipment else None,
            is_composite=item.equipment.is_composite if item.equipment else False,
            quantity=item.quantity,
            custom_name=item.custom_name,
            sort_order=item.sort_order,
            created_by=item.created_by,
        ))
    return result


@ci_router.post("/", response_model=CalcItemResponseSchema)
async def create_calc_item(
    data: CalcItemCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    item = await crud_calc_items.add_calc_item(session, data)
    await session.commit()
    item = await crud_calc_items.get_calc_item_by_id(session, item.id)
    return CalcItemResponseSchema(
        id=item.id,
        request_id=item.request_id,
        calc_type=item.calc_type,
        equipment_id=item.equipment_id,
        equipment_name=item.equipment.name if item.equipment else None,
        is_composite=item.equipment.is_composite if item.equipment else False,
        quantity=item.quantity,
        custom_name=item.custom_name,
        sort_order=item.sort_order,
        created_by=item.created_by,
    )


@ci_router.patch("/{item_id}", response_model=CalcItemResponseSchema)
async def update_calc_item(
    item_id: int, data: CalcItemUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = item_id
    item = await crud_calc_items.update_calc_item(session, data)
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    await session.commit()
    item = await crud_calc_items.get_calc_item_by_id(session, item.id)
    return CalcItemResponseSchema(
        id=item.id,
        request_id=item.request_id,
        calc_type=item.calc_type,
        equipment_id=item.equipment_id,
        equipment_name=item.equipment.name if item.equipment else None,
        is_composite=item.equipment.is_composite if item.equipment else False,
        quantity=item.quantity,
        custom_name=item.custom_name,
        sort_order=item.sort_order,
        created_by=item.created_by,
    )


@ci_router.delete("/{item_id}")
async def delete_calc_item(
    item_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_calc_items.delete_calc_item(session, item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    await session.commit()
    return {"ok": True}


@ci_router.get("/{request_id}/{calc_type}/expanded")
async def expanded_calc_items(
    request_id: int, calc_type: str,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    """Return calc items with composite equipment expanded into components."""
    items = await crud_calc_items.get_calc_items(session, request_id, calc_type)
    expanded = []
    for item in items:
        if item.equipment and item.equipment.is_composite:
            components = await crud_calc_items.get_composition_components(session, item.equipment_id)
            for comp in components:
                expanded.append({
                    "parent_name": item.custom_name or item.equipment.name,
                    "equipment_id": comp["equipment"].id,
                    "equipment_name": comp["equipment"].name,
                    "quantity": comp["quantity"] * item.quantity,
                })
        else:
            expanded.append({
                "parent_name": None,
                "equipment_id": item.equipment_id,
                "equipment_name": item.custom_name or (item.equipment.name if item.equipment else ""),
                "quantity": item.quantity,
            })
    return expanded
