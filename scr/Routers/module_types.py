from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_module_types
from scr.dbase.database import db_helper
from scr.dbase.models import ModuleTypeDefault
from scr.dbase.schemas.schemas import (
    ModuleTypeCreateSchema,
    ModuleTypeDefaultCreateSchema,
    ModuleTypeDefaultResponseSchema,
    ModuleTypeResponseSchema,
    RequestCalcItemCreateSchema,
    RequestCalcItemResponseSchema,
    RequestCalcItemUpdateSchema,
    RequestCalcResponseSchema,
    RequestCalcUpdateSchema,
)

mt_calc_router = APIRouter(tags=["ModuleTypes"])


# ── Module Types ──


@mt_calc_router.get("/api/module-types/", response_model=list[ModuleTypeResponseSchema])
async def list_module_types(session: AsyncSession = Depends(db_helper.session_dependency)):
    types = await crud_module_types.get_module_types(session)
    return [
        ModuleTypeResponseSchema(
            id=t.id,
            name=t.name,
            slug=t.slug,
            fot_item_id=t.fot_item_id,
            overhead_item_id=t.overhead_item_id,
            fot_item_name=t.fot_item.name if t.fot_item else None,
            fot_item_cost=float(t.fot_item.cost) if t.fot_item else 0,
            overhead_item_name=t.overhead_item.name if t.overhead_item else None,
            overhead_item_cost=float(t.overhead_item.cost) if t.overhead_item else 0,
            created_by=t.created_by,
        )
        for t in types
    ]


@mt_calc_router.post("/api/module-types/", response_model=ModuleTypeResponseSchema)
async def create_module_type(
    data: ModuleTypeCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    obj = await crud_module_types.add_module_type(session, data)
    await session.commit()
    return obj


@mt_calc_router.delete("/api/module-types/{type_id}")
async def delete_module_type(
    type_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_module_types.delete_module_type(session, type_id)
    if not result:
        raise HTTPException(status_code=404, detail="Тип модуля не найден")
    await session.commit()
    return {"ok": True}


@mt_calc_router.put("/api/module-types/{type_id}", response_model=ModuleTypeResponseSchema)
async def update_module_type(
    type_id: int,
    data: dict,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    mt = await crud_module_types.get_module_type_by_id(session, type_id)
    if not mt:
        raise HTTPException(status_code=404, detail="Тип модуля не найден")
    if "fot_item_id" in data:
        mt.fot_item_id = int(data["fot_item_id"]) if data["fot_item_id"] else None
    if "overhead_item_id" in data:
        mt.overhead_item_id = int(data["overhead_item_id"]) if data["overhead_item_id"] else None
    await session.flush()
    await session.commit()
    mt = await crud_module_types.get_module_type_by_id(session, type_id)
    return ModuleTypeResponseSchema(
        id=mt.id,
        name=mt.name,
        slug=mt.slug,
        fot_item_id=mt.fot_item_id,
        overhead_item_id=mt.overhead_item_id,
        fot_item_name=mt.fot_item.name if mt.fot_item else None,
        fot_item_cost=float(mt.fot_item.cost) if mt.fot_item else 0,
        overhead_item_name=mt.overhead_item.name if mt.overhead_item else None,
        overhead_item_cost=float(mt.overhead_item.cost) if mt.overhead_item else 0,
        created_by=mt.created_by,
    )


# ── Module Type Defaults ──


@mt_calc_router.get("/api/module-types/{type_id}/defaults", response_model=list[ModuleTypeDefaultResponseSchema])
async def list_defaults(
    type_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    defaults = await crud_module_types.get_defaults(session, type_id)
    return [
        ModuleTypeDefaultResponseSchema(
            id=d.id,
            module_type_id=d.module_type_id,
            module_id=d.module_id,
            quantity=d.quantity,
            module_name=d.module.name if d.module else None,
            module_price=float(d.module.total_price) if d.module else 0,
        )
        for d in defaults
    ]


@mt_calc_router.post("/api/module-types/{type_id}/defaults", response_model=ModuleTypeDefaultResponseSchema)
async def create_default(
    type_id: int,
    data: ModuleTypeDefaultCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.module_type_id = type_id
    obj = await crud_module_types.add_default(session, data)
    await session.commit()
    return ModuleTypeDefaultResponseSchema(
        id=obj.id,
        module_type_id=obj.module_type_id,
        module_id=obj.module_id,
        quantity=obj.quantity,
    )


@mt_calc_router.patch("/api/module-types/defaults/{default_id}")
async def update_default(
    default_id: int,
    data: dict,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    obj = await session.get(ModuleTypeDefault, default_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    if "quantity" in data:
        obj.quantity = int(data["quantity"])
    await session.flush()
    await session.commit()
    return {"ok": True}


@mt_calc_router.delete("/api/module-types/defaults/{default_id}")
async def delete_default(
    default_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_module_types.delete_default(session, default_id)
    if not result:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    await session.commit()
    return {"ok": True}


# ── RequestCalcs ──


@mt_calc_router.put("/api/module-types/{type_id}/fot-cost")
async def update_fot_cost(
    type_id: int,
    data: dict,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    mt = await crud_module_types.get_module_type_by_id(session, type_id)
    if not mt or not mt.fot_item:
        raise HTTPException(status_code=404, detail="ФОТ не найден")
    mt.fot_item.cost = float(data.get("cost", 0))
    from datetime import UTC, datetime

    mt.fot_item.date_modified = datetime.now(UTC)
    await session.flush()
    await session.commit()
    return {"ok": True, "cost": float(mt.fot_item.cost)}


@mt_calc_router.put("/api/module-types/{type_id}/overhead-cost")
async def update_overhead_cost(
    type_id: int,
    data: dict,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    mt = await crud_module_types.get_module_type_by_id(session, type_id)
    if not mt or not mt.overhead_item:
        raise HTTPException(status_code=404, detail="Накладные не найдены")
    mt.overhead_item.cost = float(data.get("cost", 0))
    from datetime import UTC, datetime

    mt.overhead_item.date_modified = datetime.now(UTC)
    await session.flush()
    await session.commit()
    return {"ok": True, "cost": float(mt.overhead_item.cost)}


@mt_calc_router.get("/api/request-calcs/{calc_id}", response_model=RequestCalcResponseSchema)
async def get_calc(
    calc_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    calc = await crud_module_types.get_calc_by_id(session, calc_id)
    if not calc:
        raise HTTPException(status_code=404, detail="Расчёт не найден")
    return calc


@mt_calc_router.put("/api/request-calcs/{calc_id}", response_model=RequestCalcResponseSchema)
async def update_calc(
    calc_id: int,
    data: RequestCalcUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = calc_id
    result = await crud_module_types.update_calc(session, data)
    if not result:
        raise HTTPException(status_code=404, detail="Расчёт не найден")
    await session.commit()
    return result


@mt_calc_router.post("/api/request-calcs/{calc_id}/items", response_model=RequestCalcItemResponseSchema)
async def add_calc_item(
    calc_id: int,
    data: RequestCalcItemCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.calc_id = calc_id
    obj = await crud_module_types.add_calc_item(session, data)
    await session.commit()
    await session.refresh(obj, attribute_names=["module"])
    return RequestCalcItemResponseSchema(
        id=obj.id,
        calc_id=obj.calc_id,
        module_id=obj.module_id,
        quantity=obj.quantity,
        module_name=obj.module.name if obj.module else None,
        module_price=float(obj.module.total_price) if obj.module else 0,
    )


@mt_calc_router.patch("/api/request-calcs/items/{item_id}", response_model=RequestCalcItemResponseSchema)
async def update_calc_item(
    item_id: int,
    data: RequestCalcItemUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = item_id
    result = await crud_module_types.update_calc_item(session, data)
    if not result:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    await session.commit()
    await session.refresh(result, attribute_names=["module"])
    return RequestCalcItemResponseSchema(
        id=result.id,
        calc_id=result.calc_id,
        module_id=result.module_id,
        quantity=result.quantity,
        module_name=result.module.name if result.module else None,
        module_price=float(result.module.total_price) if result.module else 0,
    )


@mt_calc_router.delete("/api/request-calcs/items/{item_id}")
async def delete_calc_item(
    item_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_module_types.delete_calc_item(session, item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    await session.commit()
    return {"ok": True}
