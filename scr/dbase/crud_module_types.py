from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase.models import InvoiceItem, ModuleType, ModuleTypeDefault, PayrollItem, RequestCalc, RequestCalcItem
from scr.dbase.schemas.schemas import (
    ModuleTypeCreateSchema,
    ModuleTypeDefaultCreateSchema,
    RequestCalcItemCreateSchema,
    RequestCalcItemUpdateSchema,
    RequestCalcUpdateSchema,
)

# ── ModuleType ──


async def get_module_types(session: AsyncSession) -> list[ModuleType]:
    stmt = (
        select(ModuleType)
        .options(selectinload(ModuleType.fot_item), selectinload(ModuleType.overhead_item))
        .order_by(ModuleType.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_module_type_by_id(session: AsyncSession, type_id: int) -> ModuleType | None:
    stmt = (
        select(ModuleType)
        .where(ModuleType.id == type_id)
        .options(selectinload(ModuleType.fot_item), selectinload(ModuleType.overhead_item))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_module_type_by_slug(session: AsyncSession, slug: str) -> ModuleType | None:
    stmt = (
        select(ModuleType)
        .where(ModuleType.slug == slug)
        .options(selectinload(ModuleType.fot_item), selectinload(ModuleType.overhead_item))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_module_type(
    session: AsyncSession, data: ModuleTypeCreateSchema, created_by: str | None = None
) -> ModuleType:
    existing = await get_module_type_by_slug(session, data.slug)
    if existing:
        return existing
    obj = ModuleType(**data.model_dump())
    obj.created_by = created_by
    session.add(obj)
    await session.flush()
    return obj


async def delete_module_type(session: AsyncSession, type_id: int) -> ModuleType | None:
    obj = await get_module_type_by_id(session, type_id)
    if obj:
        await session.delete(obj)
        await session.flush()
    return obj


async def get_or_create_fot_item(session: AsyncSession, type_name: str) -> PayrollItem:
    name = f"ФОТ_{type_name}"
    stmt = select(PayrollItem).where(PayrollItem.name == name)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if item:
        return item
    item = PayrollItem(name=name, cost=0)
    session.add(item)
    await session.flush()
    return item


async def get_or_create_overhead_item(session: AsyncSession, type_name: str) -> InvoiceItem:
    name = f"Накладные_{type_name}"
    stmt = select(InvoiceItem).where(InvoiceItem.name == name)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if item:
        return item
    item = InvoiceItem(name=name, cost=0)
    session.add(item)
    await session.flush()
    return item


# ── ModuleTypeDefault ──


async def get_defaults(session: AsyncSession, module_type_id: int) -> list[ModuleTypeDefault]:
    stmt = (
        select(ModuleTypeDefault)
        .where(ModuleTypeDefault.module_type_id == module_type_id)
        .options(selectinload(ModuleTypeDefault.module))
        .order_by(ModuleTypeDefault.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def add_default(session: AsyncSession, data: ModuleTypeDefaultCreateSchema) -> ModuleTypeDefault:
    obj = ModuleTypeDefault(**data.model_dump())
    session.add(obj)
    await session.flush()
    return obj


async def delete_default(session: AsyncSession, default_id: int) -> ModuleTypeDefault | None:
    obj = await session.get(ModuleTypeDefault, default_id)
    if obj:
        await session.delete(obj)
        await session.flush()
    return obj


# ── RequestCalc ──


async def get_or_create_calc(session: AsyncSession, request_id: int, module_type_id: int) -> RequestCalc:
    stmt = (
        select(RequestCalc)
        .where(RequestCalc.request_id == request_id, RequestCalc.module_type_id == module_type_id)
        .options(selectinload(RequestCalc.items).selectinload(RequestCalcItem.module))
    )
    result = await session.execute(stmt)
    calc = result.scalar_one_or_none()

    # Get module type with linked items
    mod_type = await get_module_type_by_id(session, module_type_id)

    if calc:
        # Refresh fot/overhead from linked items if calc values are still 0
        if mod_type and mod_type.fot_item and float(calc.fot) == 0 and float(mod_type.fot_item.cost) > 0:
            calc.fot = float(mod_type.fot_item.cost)
        if mod_type and mod_type.overhead_item and float(calc.overhead) == 0 and float(mod_type.overhead_item.cost) > 0:
            calc.overhead = float(mod_type.overhead_item.cost)
        return calc

    fot_val = float(mod_type.fot_item.cost) if mod_type and mod_type.fot_item else 0
    overhead_val = float(mod_type.overhead_item.cost) if mod_type and mod_type.overhead_item else 0

    calc = RequestCalc(
        request_id=request_id,
        module_type_id=module_type_id,
        fot=fot_val,
        overhead=overhead_val,
    )
    session.add(calc)
    await session.flush()

    # Copy defaults
    if mod_type:
        defaults = await get_defaults(session, module_type_id)
        for d in defaults:
            item = RequestCalcItem(calc_id=calc.id, module_id=d.module_id, quantity=d.quantity)
            session.add(item)
        await session.flush()

    # Reload with items eagerly loaded
    stmt = (
        select(RequestCalc)
        .where(RequestCalc.id == calc.id)
        .options(selectinload(RequestCalc.items).selectinload(RequestCalcItem.module))
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def get_calc_by_id(session: AsyncSession, calc_id: int) -> RequestCalc | None:
    stmt = (
        select(RequestCalc)
        .where(RequestCalc.id == calc_id)
        .options(selectinload(RequestCalc.items).selectinload(RequestCalcItem.module))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_calc(session: AsyncSession, data: RequestCalcUpdateSchema) -> RequestCalc | None:
    calc = await session.get(RequestCalc, data.id)
    if not calc:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        if field != "id" and hasattr(calc, field):
            setattr(calc, field, value)
    await session.flush()
    return calc


# ── RequestCalcItem ──


async def add_calc_item(session: AsyncSession, data: RequestCalcItemCreateSchema) -> RequestCalcItem:
    obj = RequestCalcItem(**data.model_dump())
    session.add(obj)
    await session.flush()
    return obj


async def update_calc_item(session: AsyncSession, data: RequestCalcItemUpdateSchema) -> RequestCalcItem | None:
    obj = await session.get(RequestCalcItem, data.id)
    if not obj:
        return None
    obj.quantity = data.quantity
    await session.flush()
    return obj


async def delete_calc_item(session: AsyncSession, item_id: int) -> RequestCalcItem | None:
    obj = await session.get(RequestCalcItem, item_id)
    if obj:
        await session.delete(obj)
        await session.flush()
    return obj
