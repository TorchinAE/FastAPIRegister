from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import CalcItem, Equipment, EquipmentComposition
from scr.dbase.schemas.schemas import CalcItemCreateSchema, CalcItemUpdateSchema


async def get_calc_items(session: AsyncSession, request_id: int, calc_type: str) -> list[CalcItem]:
    stmt = (
        select(CalcItem)
        .options(selectinload(CalcItem.equipment))
        .where(CalcItem.request_id == request_id, CalcItem.calc_type == calc_type)
        .order_by(CalcItem.sort_order, CalcItem.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_calc_item_by_id(session: AsyncSession, item_id: int) -> CalcItem | None:
    stmt = select(CalcItem).options(selectinload(CalcItem.equipment)).where(CalcItem.id == item_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_calc_item(session: AsyncSession, schema: CalcItemCreateSchema, created_by: str = None) -> CalcItem:
    item = CalcItem(
        request_id=schema.request_id,
        calc_type=schema.calc_type,
        equipment_id=schema.equipment_id,
        quantity=schema.quantity,
        custom_name=schema.custom_name,
        created_by=created_by,
    )
    session.add(item)
    await session.flush()
    return item


async def update_calc_item(session: AsyncSession, schema: CalcItemUpdateSchema) -> CalcItem | None:
    item = await session.get(CalcItem, schema.id)
    if not item:
        return None
    data = schema.model_dump(exclude_unset=True, exclude={"id"})
    for key, value in data.items():
        setattr(item, key, value)
    await session.flush()
    return item


async def delete_calc_item(session: AsyncSession, item_id: int) -> CalcItem | None:
    item = await session.get(CalcItem, item_id)
    if not item:
        return None
    await session.delete(item)
    await session.flush()
    return item


async def get_composition_components(session: AsyncSession, equipment_id: int) -> list[dict]:
    """Recursively expand composite equipment into simple components with quantities."""
    stmt = (
        select(EquipmentComposition)
        .options(selectinload(EquipmentComposition.child))
        .where(EquipmentComposition.parent_id == equipment_id)
    )
    result = await session.execute(stmt)
    compositions = list(result.scalars().all())

    components = []
    for comp in compositions:
        child = comp.child
        if child.is_composite:
            sub_components = await get_composition_components(session, child.id)
            for sc in sub_components:
                components.append({
                    "equipment": sc["equipment"],
                    "quantity": sc["quantity"] * comp.quantity,
                })
        else:
            components.append({
                "equipment": child,
                "quantity": comp.quantity,
            })
    return components
