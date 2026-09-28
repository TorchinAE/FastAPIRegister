from sqlalchemy import Result, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase.models import Module, ModuleItem
from scr.dbase.schemas.schemas import ModuleCreateSchema, ModuleItemCreateSchema, ModuleUpdateSchema


async def get_modules(
    session: AsyncSession, search: str | None = None, page: int = 1, per_page: int = 20
) -> tuple[list[Module], int]:
    stmt = (
        select(Module)
        .options(
            selectinload(Module.items).selectinload(ModuleItem.material),
            selectinload(Module.items).selectinload(ModuleItem.sub_module),
        )
        .order_by(Module.name)
    )
    count_stmt = select(func.count(Module.id))

    if search:
        filter_cond = Module.name.ilike(f"%{search}%")
        stmt = stmt.where(filter_cond)
        count_stmt = count_stmt.where(filter_cond)

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().unique().all()), total


async def get_all_modules(session: AsyncSession) -> list[Module]:
    stmt = (
        select(Module)
        .options(
            selectinload(Module.items).selectinload(ModuleItem.material),
            selectinload(Module.items).selectinload(ModuleItem.sub_module),
        )
        .order_by(Module.name)
    )
    result: Result = await session.execute(stmt)
    return list(result.scalars().unique().all())


async def get_module_by_id(session: AsyncSession, mod_id: int) -> Module | None:
    stmt = (
        select(Module)
        .where(Module.id == mod_id)
        .options(
            selectinload(Module.items).selectinload(ModuleItem.material),
            selectinload(Module.items).selectinload(ModuleItem.sub_module),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_module_by_name(session: AsyncSession, name: str) -> Module | None:
    stmt = select(Module).where(Module.name == name)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_module(session: AsyncSession, in_mod: ModuleCreateSchema, created_by: str | None = None) -> Module:
    check_mod = await get_module_by_name(session, in_mod.name)
    if check_mod:
        return check_mod
    mod = Module(name=in_mod.name)
    mod.created_by = created_by
    session.add(mod)
    await session.flush()
    return mod


async def update_module(session: AsyncSession, upd_mod: ModuleUpdateSchema) -> Module | None:
    check_mod = await get_module_by_id(session, upd_mod.id)
    if not check_mod:
        return None
    if upd_mod.name is not None:
        check_mod.name = upd_mod.name
    await session.flush()
    return check_mod


async def delete_module(session: AsyncSession, mod_id: int) -> Module | None:
    mod = await session.get(Module, mod_id)
    if mod:
        await session.delete(mod)
        await session.flush()
    return mod


async def add_module_item(session: AsyncSession, module_id: int, item_in: ModuleItemCreateSchema) -> ModuleItem | None:
    mod = await get_module_by_id(session, module_id)
    if not mod:
        return None
    item = ModuleItem(
        module_id=module_id,
        material_id=item_in.material_id,
        sub_module_id=item_in.sub_module_id,
        quantity=item_in.quantity or 1,
    )
    session.add(item)
    await session.flush()
    return item


async def update_module_item_quantity(session: AsyncSession, item_id: int, quantity: int) -> ModuleItem | None:
    item = await session.get(ModuleItem, item_id)
    if item:
        item.quantity = quantity
        await session.flush()
    return item


async def delete_module_item(session: AsyncSession, item_id: int) -> ModuleItem | None:
    item = await session.get(ModuleItem, item_id)
    if item:
        await session.delete(item)
        await session.flush()
    return item


async def get_module_items(session: AsyncSession, module_id: int) -> list[ModuleItem]:
    stmt = (
        select(ModuleItem)
        .where(ModuleItem.module_id == module_id)
        .options(selectinload(ModuleItem.material), selectinload(ModuleItem.sub_module))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
