from sqlalchemy import select, Result, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import Equipment, EquipmentComposition
from scr.dbase.schemas.schemas import EquipmentCreateSchema, EquipmentUpdateSchema


async def get_equipment_list(
    session: AsyncSession, search: str | None = None, section_id: int | None = None,
    is_composite: bool | None = None, page: int = 1, per_page: int = 20
) -> tuple[list[Equipment], int]:
    stmt = select(Equipment).order_by(Equipment.name)
    count_stmt = select(func.count(Equipment.id))

    if search:
        filter_cond = Equipment.name.ilike(f"%{search}%")
        stmt = stmt.where(filter_cond)
        count_stmt = count_stmt.where(filter_cond)
    if section_id is not None:
        stmt = stmt.where(Equipment.section_id == section_id)
        count_stmt = count_stmt.where(Equipment.section_id == section_id)
    if is_composite is not None:
        stmt = stmt.where(Equipment.is_composite == is_composite)
        count_stmt = count_stmt.where(Equipment.is_composite == is_composite)

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_all_equipment(session: AsyncSession) -> list[Equipment]:
    stmt = select(Equipment).order_by(Equipment.name)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_equipment_by_id(session: AsyncSession, eq_id: int) -> Equipment | None:
    return await session.get(Equipment, eq_id)


async def get_equipment_by_name(session: AsyncSession, name: str) -> Equipment | None:
    stmt = select(Equipment).where(Equipment.name == name)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_equipment(
    session: AsyncSession, in_eq: EquipmentCreateSchema, created_by: str | None = None
) -> Equipment:
    check_eq = await get_equipment_by_name(session, in_eq.name)
    if check_eq:
        return check_eq
    eq = Equipment(**in_eq.model_dump())
    eq.created_by = created_by
    session.add(eq)
    await session.flush()
    return eq


async def update_equipment(
    session: AsyncSession, upd_eq: EquipmentUpdateSchema
) -> Equipment | None:
    check_eq = await get_equipment_by_id(session, upd_eq.id)
    if not check_eq:
        return None
    for field, value in upd_eq.model_dump(exclude_unset=True).items():
        if field != "id" and hasattr(check_eq, field):
            setattr(check_eq, field, value)
    await session.flush()
    return check_eq


async def delete_equipment(session: AsyncSession, eq_id: int) -> Equipment | None:
    eq = await session.get(Equipment, eq_id)
    if eq:
        await session.delete(eq)
        await session.flush()
    return eq


async def set_composition(session: AsyncSession, parent_id: int, components: list[dict]) -> Equipment | None:
    parent = await session.get(Equipment, parent_id)
    if not parent:
        return None
    # Remove old composition
    stmt = select(EquipmentComposition).where(EquipmentComposition.parent_id == parent_id)
    result = await session.execute(stmt)
    for old in result.scalars().all():
        await session.delete(old)
    # Add new composition
    for comp in components:
        session.add(EquipmentComposition(
            parent_id=parent_id,
            child_id=comp["child_id"],
            quantity=comp.get("quantity", 1),
        ))
    parent.is_composite = True
    await session.flush()
    return parent


async def get_composition(session: AsyncSession, parent_id: int) -> list[EquipmentComposition]:
    stmt = (
        select(EquipmentComposition)
        .options(selectinload(EquipmentComposition.child))
        .where(EquipmentComposition.parent_id == parent_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
