from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import CalcItem, CalcProduct, CalcProductComponent
from scr.dbase.schemas.schemas import CalcItemCreateSchema, CalcItemUpdateSchema


async def get_calc_items(session: AsyncSession, request_id: int, calc_type: str) -> list[CalcItem]:
    stmt = (
        select(CalcItem)
        .options(selectinload(CalcItem.product).selectinload(CalcProduct.components).selectinload(CalcProductComponent.equipment))
        .where(CalcItem.request_id == request_id, CalcItem.calc_type == calc_type)
        .order_by(CalcItem.sort_order, CalcItem.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_calc_item_by_id(session: AsyncSession, item_id: int) -> CalcItem | None:
    stmt = select(CalcItem).options(
        selectinload(CalcItem.product).selectinload(CalcProduct.components).selectinload(CalcProductComponent.equipment)
    ).where(CalcItem.id == item_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_calc_item(session: AsyncSession, schema: CalcItemCreateSchema, created_by: str = None) -> CalcItem:
    item = CalcItem(
        request_id=schema.request_id, calc_type=schema.calc_type,
        product_id=schema.product_id, quantity=schema.quantity, created_by=created_by,
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
