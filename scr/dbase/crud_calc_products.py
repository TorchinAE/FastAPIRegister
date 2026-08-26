from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import CalcProduct, CalcProductComponent, Equipment
from scr.dbase.schemas.schemas import CalcProductCreateSchema, CalcProductUpdateSchema


async def get_products(session: AsyncSession, section_id: int = None, search: str = None,
                       page: int = 1, per_page: int = 20) -> tuple[list[CalcProduct], int]:
    stmt = select(CalcProduct).options(selectinload(CalcProduct.components)).order_by(CalcProduct.name)
    count_stmt = select(func.count(CalcProduct.id))
    if section_id:
        stmt = stmt.where(CalcProduct.section_id == section_id)
        count_stmt = count_stmt.where(CalcProduct.section_id == section_id)
    if search:
        stmt = stmt.where(CalcProduct.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(CalcProduct.name.ilike(f"%{search}%"))
    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_product_by_id(session: AsyncSession, product_id: int) -> CalcProduct | None:
    stmt = select(CalcProduct).options(
        selectinload(CalcProduct.components).selectinload(CalcProductComponent.equipment),
        selectinload(CalcProduct.section),
    ).where(CalcProduct.id == product_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_product(session: AsyncSession, schema: CalcProductCreateSchema, created_by: str = None) -> CalcProduct:
    product = CalcProduct(name=schema.name, section_id=schema.section_id, created_by=created_by)
    session.add(product)
    await session.flush()
    for comp in schema.components:
        session.add(CalcProductComponent(
            product_id=product.id, equipment_id=comp.equipment_id, quantity=comp.quantity
        ))
    await session.flush()
    return product


async def update_product(session: AsyncSession, schema: CalcProductUpdateSchema) -> CalcProduct | None:
    product = await get_product_by_id(session, schema.id)
    if not product:
        return None
    if schema.name is not None:
        product.name = schema.name
    if schema.section_id is not None:
        product.section_id = schema.section_id
    if schema.components is not None:
        for old in product.components:
            await session.delete(old)
        for comp in schema.components:
            session.add(CalcProductComponent(
                product_id=product.id, equipment_id=comp.equipment_id, quantity=comp.quantity
            ))
    await session.flush()
    return product


async def delete_product(session: AsyncSession, product_id: int) -> CalcProduct | None:
    product = await session.get(CalcProduct, product_id)
    if not product:
        return None
    await session.delete(product)
    await session.flush()
    return product


async def expand_product(session: AsyncSession, product_id: int, multiplier: int = 1) -> list[dict]:
    """Expand a product into its equipment components with quantities."""
    product = await get_product_by_id(session, product_id)
    if not product:
        return []
    if not product.components:
        return [{"equipment_name": product.name, "quantity": multiplier}]
    result = []
    for comp in product.components:
        result.append({
            "equipment_name": comp.equipment.name if comp.equipment else "?",
            "quantity": comp.quantity * multiplier,
        })
    return result
