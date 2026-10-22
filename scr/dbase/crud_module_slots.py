"""Обязательные строки разделов расчёта (КСО, КРУ, ЩО, ...): одна строка — один модуль."""

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase.models import (
    MaterialType,
    Module,
    ModuleTypeDefault,
    ModuleTypeSlot,
    RequestCalc,
    RequestCalcItem,
)
from scr.dbase.schemas.schemas import ModuleTypeSlotCreateSchema, ModuleTypeSlotUpdateSchema


async def get_slots(session: AsyncSession, module_type_id: int) -> list[ModuleTypeSlot]:
    stmt = (
        select(ModuleTypeSlot)
        .where(ModuleTypeSlot.module_type_id == module_type_id)
        .options(selectinload(ModuleTypeSlot.material_types))
        .order_by(ModuleTypeSlot.sort_order, ModuleTypeSlot.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_slot_by_id(session: AsyncSession, slot_id: int) -> ModuleTypeSlot | None:
    stmt = (
        select(ModuleTypeSlot).where(ModuleTypeSlot.id == slot_id).options(selectinload(ModuleTypeSlot.material_types))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _material_types(session: AsyncSession, ids: list[int]) -> list[MaterialType]:
    if not ids:
        return []
    return list((await session.execute(select(MaterialType).where(MaterialType.id.in_(ids)))).scalars().all())


async def add_slot(session: AsyncSession, data: ModuleTypeSlotCreateSchema) -> ModuleTypeSlot:
    slots = await get_slots(session, data.module_type_id)
    name = data.name.strip()
    for slot in slots:
        if slot.name.strip().lower() == name.lower():
            return slot
    slot = ModuleTypeSlot(
        module_type_id=data.module_type_id,
        name=name,
        hidden=data.hidden,
        purpose=(data.purpose or "").strip() or None,
        sort_order=max((s.sort_order for s in slots), default=0) + 1,
    )
    slot.material_types = await _material_types(session, data.material_type_ids)
    session.add(slot)
    await session.flush()
    return await get_slot_by_id(session, slot.id)


async def update_slot(session: AsyncSession, slot_id: int, data: ModuleTypeSlotUpdateSchema) -> ModuleTypeSlot | None:
    slot = await get_slot_by_id(session, slot_id)
    if not slot:
        return None
    if data.name is not None and data.name.strip():
        slot.name = data.name.strip()
    if data.hidden is not None:
        slot.hidden = data.hidden
    if data.material_type_ids is not None:
        slot.material_types = await _material_types(session, data.material_type_ids)
    if "purpose" in data.model_fields_set:
        slot.purpose = (data.purpose or "").strip() or None
    await session.flush()
    return slot


async def move_slot(session: AsyncSession, slot_id: int, direction: int) -> ModuleTypeSlot | None:
    """Сдвигает строку вверх (direction < 0) или вниз (direction > 0)."""
    slot = await session.get(ModuleTypeSlot, slot_id)
    if not slot:
        return None
    slots = await get_slots(session, slot.module_type_id)
    idx = next(i for i, s in enumerate(slots) if s.id == slot_id)
    target = idx + (1 if direction > 0 else -1)
    if 0 <= target < len(slots):
        slots[idx], slots[target] = slots[target], slots[idx]
    for i, s in enumerate(slots, start=1):
        s.sort_order = i
    await session.flush()
    return slot


async def delete_slot(session: AsyncSession, slot_id: int) -> ModuleTypeSlot | None:
    """Удаляет строку и её модуль по умолчанию; в расчётах модули строки остаются обычными строками."""
    slot = await session.get(ModuleTypeSlot, slot_id)
    if slot:
        await session.execute(delete(ModuleTypeDefault).where(ModuleTypeDefault.slot_id == slot_id))
        await session.execute(update(RequestCalcItem).where(RequestCalcItem.slot_id == slot_id).values(slot_id=None))
        await session.delete(slot)
        await session.flush()
    return slot


def allowed_module(slot: ModuleTypeSlot, module: Module) -> bool:
    """Модуль подходит в строку, если его тип среди выбранных (типы не выбраны — подходит любой)."""
    type_ids = {t.id for t in slot.material_types}
    return not type_ids or module.material_type_id in type_ids


def slot_json(slot: ModuleTypeSlot) -> dict:
    return {
        "id": slot.id,
        "name": slot.name,
        "hidden": bool(slot.hidden),
        "purpose": slot.purpose or "",
        "type_ids": [t.id for t in slot.material_types],
        "type_names": [t.name for t in slot.material_types],
    }


def order_by_slots(items: list, slots: list[ModuleTypeSlot]) -> list:
    """Общий порядок: сначала обязательные строки по порядку, затем остальные модули."""
    order = {s.id: i for i, s in enumerate(slots)}
    return sorted(items, key=lambda it: (it.slot_id not in order, order.get(it.slot_id, 0), it.id))


# ── Модуль строки: в «по умолчанию» и в блоке расчёта ──


async def _check_module(session: AsyncSession, slot: ModuleTypeSlot, module_id: int | None) -> Module | None:
    if module_id is None:
        return None
    module = await session.get(Module, module_id)
    if not module:
        raise ValueError("Модуль не найден")
    if not allowed_module(slot, module):
        raise ValueError("Модуль не подходит по типу для этой строки")
    return module


async def set_slot_default(
    session: AsyncSession, slot: ModuleTypeSlot, module_id: int | None, quantity: int, template_id: int | None = None
) -> ModuleTypeDefault | None:
    """Модуль строки в шаблоне (не задан — в основном шаблоне раздела); module_id=None — строка пустая."""
    from scr.dbase.crud_module_templates import resolve_template

    await _check_module(session, slot, module_id)
    tpl = await resolve_template(session, slot.module_type_id, template_id)
    stmt = select(ModuleTypeDefault).where(
        ModuleTypeDefault.slot_id == slot.id, ModuleTypeDefault.template_id == tpl.id
    )
    obj = (await session.execute(stmt)).scalar_one_or_none()
    if module_id is None:
        if obj:
            await session.delete(obj)
            await session.flush()
        return None
    if not obj:
        obj = ModuleTypeDefault(
            module_type_id=slot.module_type_id, slot_id=slot.id, module_id=module_id, template_id=tpl.id
        )
        session.add(obj)
    obj.module_id = module_id
    obj.quantity = quantity
    await session.flush()
    return obj


async def set_calc_slot(
    session: AsyncSession, calc_id: int, slot: ModuleTypeSlot, module_id: int | None, quantity: int
) -> RequestCalcItem | None:
    """Модуль строки в блоке расчёта; module_id=None — строка пустая."""
    await _check_module(session, slot, module_id)
    stmt = select(RequestCalcItem).where(RequestCalcItem.calc_id == calc_id, RequestCalcItem.slot_id == slot.id)
    obj = (await session.execute(stmt)).scalar_one_or_none()
    if module_id is None:
        if obj:
            await session.delete(obj)
            await session.flush()
        return None
    if not obj:
        obj = RequestCalcItem(calc_id=calc_id, slot_id=slot.id, module_id=module_id)
        session.add(obj)
    obj.module_id = module_id
    obj.quantity = quantity
    await session.flush()
    return obj


async def sync_hidden_slots(session: AsyncSession, request_id: int) -> bool:
    """Скрытые строки в расчётах заявки всегда как в шаблоне блока (нет шаблона — основной шаблон раздела).

    Пересчитывает итоги изменённых блоков.
    """
    from scr.dbase import crud_module_types
    from scr.dbase.crud_module_templates import get_templates
    from scr.dbase.crud_modules import get_module_prices

    hidden = (await session.execute(select(ModuleTypeSlot).where(ModuleTypeSlot.hidden.is_(True)))).scalars().all()
    if not hidden:
        return False
    hidden_by_type: dict[int, list[int]] = {}
    for slot in hidden:
        hidden_by_type.setdefault(slot.module_type_id, []).append(slot.id)
    used_types = await session.execute(
        select(RequestCalc.module_type_id)
        .where(RequestCalc.request_id == request_id, RequestCalc.module_type_id.in_(hidden_by_type))
        .distinct()
    )
    templates_by_type = {t: await get_templates(session, t) for t in used_types.scalars().all()}
    if not templates_by_type:
        return False
    main_template = {t: tpls[0].id for t, tpls in templates_by_type.items()}
    template_ids = {tpl.id for tpls in templates_by_type.values() for tpl in tpls}
    defaults_stmt = select(ModuleTypeDefault).where(ModuleTypeDefault.slot_id.in_([s.id for s in hidden]))
    defaults = {
        (d.template_id, d.slot_id): d
        for d in (await session.execute(defaults_stmt)).scalars().all()
        if d.template_id in template_ids
    }

    calcs_stmt = (
        select(RequestCalc)
        .where(RequestCalc.request_id == request_id, RequestCalc.module_type_id.in_(hidden_by_type))
        .options(selectinload(RequestCalc.items), selectinload(RequestCalc.module_type))
    )
    changed_calcs: list[RequestCalc] = []
    for calc in (await session.execute(calcs_stmt)).scalars().all():
        items = {it.slot_id: it for it in calc.items if it.slot_id is not None}
        tpl_id = calc.template_id if calc.template_id in template_ids else main_template[calc.module_type_id]
        changed = False
        for slot_id in hidden_by_type[calc.module_type_id]:
            d, it = defaults.get((tpl_id, slot_id)), items.get(slot_id)
            if d is None:
                if it is not None:
                    calc.items.remove(it)
                    changed = True
            elif it is None:
                calc.items.append(RequestCalcItem(slot_id=slot_id, module_id=d.module_id, quantity=d.quantity))
                changed = True
            elif (it.module_id, it.quantity) != (d.module_id, d.quantity):
                it.module_id, it.quantity = d.module_id, d.quantity
                changed = True
        if changed:
            changed_calcs.append(calc)
    if not changed_calcs:
        return False

    await session.flush()
    prices = await get_module_prices(session)
    for calc in changed_calcs:
        works = calc.module_type.slug in crud_module_types.WORKS_SECTIONS
        total = crud_module_types.calc_base_cost(calc, prices, works=works)
        calc.total_cost = round(total, 2)
        calc.final_price = round(total * (1 + float(calc.profitability_percent or 0) / 100), 2)
    await session.flush()
    for type_id in {c.module_type_id for c in changed_calcs}:
        await crud_module_types.recalc_section_cost(session, request_id, type_id)
    return True
