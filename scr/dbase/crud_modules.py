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
    if upd_mod.nom_tok_manual is False:
        # Вернуть автоматический расчёт ном. тока
        check_mod.nom_tok_manual = False
        await recalc_nom_tok(session)
    elif upd_mod.nom_tok is not None:
        check_mod.nom_tok = upd_mod.nom_tok
        check_mod.nom_tok_manual = True
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


# ── Цены и ном. ток модулей с учётом вложенности ──


async def load_tree(session: AsyncSession) -> tuple[dict[int, list[tuple]], dict[int, tuple[float, int]]]:
    """Состав всех модулей одной выборкой: {module_id: [(material_id, sub_module_id, qty)]} и данные материалов."""
    from scr.dbase.models import Material

    items_result = await session.execute(
        select(ModuleItem.module_id, ModuleItem.material_id, ModuleItem.sub_module_id, ModuleItem.quantity)
    )
    tree: dict[int, list[tuple]] = {}
    for module_id, material_id, sub_module_id, qty in items_result.all():
        tree.setdefault(module_id, []).append((material_id, sub_module_id, qty))
    mat_result = await session.execute(select(Material.id, Material.price, Material.nom_tok))
    materials = {mid: (float(price or 0), nom_tok or 0) for mid, price, nom_tok in mat_result.all()}
    return tree, materials


async def get_module_prices(session: AsyncSession) -> dict[int, float]:
    """Стоимость каждого модуля (рекурсивно по подмодулям, с защитой от циклов)."""
    tree, materials = await load_tree(session)
    prices: dict[int, float] = {}

    def price_of(module_id: int, stack: frozenset) -> float:
        if module_id in prices:
            return prices[module_id]
        if module_id in stack:
            return 0.0
        total = 0.0
        for material_id, sub_module_id, qty in tree.get(module_id, []):
            if material_id is not None:
                total += materials.get(material_id, (0.0, 0))[0] * qty
            elif sub_module_id is not None:
                total += price_of(sub_module_id, stack | {module_id}) * qty
        prices[module_id] = total
        return total

    ids = await session.execute(select(Module.id))
    for (module_id,) in ids.all():
        price_of(module_id, frozenset())
    return prices


async def recalc_nom_tok(session: AsyncSession) -> None:
    """Пересчитывает ном. ток модулей без ручного значения: максимум из материалов состава (с подмодулями)."""
    tree, materials = await load_tree(session)
    modules = list((await session.execute(select(Module))).scalars().all())
    by_id = {m.id: m for m in modules}
    auto: dict[int, int] = {}

    def tok_of(module_id: int, stack: frozenset) -> int:
        mod = by_id.get(module_id)
        if mod is not None and mod.nom_tok_manual:
            return mod.nom_tok or 0
        if module_id in auto:
            return auto[module_id]
        if module_id in stack:
            return 0
        best = 0
        for material_id, sub_module_id, _qty in tree.get(module_id, []):
            if material_id is not None:
                best = max(best, materials.get(material_id, (0.0, 0))[1])
            elif sub_module_id is not None:
                best = max(best, tok_of(sub_module_id, stack | {module_id}))
        auto[module_id] = best
        return best

    for mod in modules:
        if not mod.nom_tok_manual:
            value = tok_of(mod.id, frozenset())
            if mod.nom_tok != value:
                mod.nom_tok = value
    await session.flush()
