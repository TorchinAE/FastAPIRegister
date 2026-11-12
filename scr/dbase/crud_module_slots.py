"""Обязательные строки разделов расчёта (КСО, КРУ, ЩО, ...): одна строка — один модуль.

Копии блоков строк делаются в блоке расчёта или в шаблоне и существуют только там: строки раздела
не добавляются. Модуль копии — RequestCalcItem / ModuleTypeDefault с copy_no > 0, количество копий
блока — slot_copies блока расчёта / шаблона ({id первой строки блока: количество})."""

import json

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.constants import SLOT_FILTERS
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


def _filters(keys: list[str]) -> str | None:
    """Известные ключи фильтров в порядке SLOT_FILTERS через запятую."""
    return ",".join(k for k in SLOT_FILTERS if k in keys) or None


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
        filters=_filters(data.filters),
        color=data.color or None,
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
    if data.filters is not None:
        slot.filters = _filters(data.filters)
    if "color" in data.model_fields_set:
        slot.color = data.color or None
    if data.join_prev is not None:
        slot.join_prev = data.join_prev
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


async def copy_slot_group(session: AsyncSession, slot_id: int) -> list[ModuleTypeSlot] | None:
    """Копия блока объединённых строк (или одной строки) в разделе — сразу за блоком (страница
    «Обязательные строки»): настройки строк и их модули во всех шаблонах. Названия — «… (копия)»,
    при совпадении — с номером. Копия блока в расчёте или шаблоне — copy_group_in."""
    slot = await session.get(ModuleTypeSlot, slot_id)
    if not slot:
        return None
    slots = await get_slots(session, slot.module_type_id)
    idx = next(i for i, s in enumerate(slots) if s.id == slot_id)
    start = idx
    while start > 0 and slots[start].join_prev:
        start -= 1
    end = idx + 1
    while end < len(slots) and slots[end].join_prev:
        end += 1
    group = slots[start:end]

    names = {s.name.strip().lower() for s in slots}
    copies: list[ModuleTypeSlot] = []
    for i, src in enumerate(group):
        name, n = f"{src.name} (копия)", 2
        while name.lower() in names:
            name, n = f"{src.name} (копия {n})", n + 1
        names.add(name.lower())
        copy = ModuleTypeSlot(
            module_type_id=src.module_type_id,
            name=name,
            hidden=src.hidden,
            filters=src.filters,
            color=src.color,
            join_prev=i > 0,
        )
        copy.material_types = list(src.material_types)
        session.add(copy)
        copies.append(copy)
    await session.flush()

    # Модули строк в шаблонах по умолчанию
    defaults = (
        (await session.execute(select(ModuleTypeDefault).where(ModuleTypeDefault.slot_id.in_([s.id for s in group]))))
        .scalars()
        .all()
    )
    copy_of = {src.id: copy.id for src, copy in zip(group, copies, strict=True)}
    for d in defaults:
        if d.copy_no:
            continue
        session.add(
            ModuleTypeDefault(
                module_type_id=d.module_type_id,
                template_id=d.template_id,
                slot_id=copy_of[d.slot_id],
                module_id=d.module_id,
                quantity=d.quantity,
            )
        )
    order = slots[:end] + copies + slots[end:]
    for i, s in enumerate(order, start=1):
        s.sort_order = i
    await session.flush()
    return copies


async def delete_slot(session: AsyncSession, slot_id: int) -> ModuleTypeSlot | None:
    """Удаляет строку и её модуль по умолчанию; в расчётах модули строки остаются обычными строками."""
    slot = await session.get(ModuleTypeSlot, slot_id)
    if slot:
        await session.execute(delete(ModuleTypeDefault).where(ModuleTypeDefault.slot_id == slot_id))
        await session.execute(
            update(RequestCalcItem).where(RequestCalcItem.slot_id == slot_id).values(slot_id=None, copy_no=0)
        )
        await session.delete(slot)
        await session.flush()
    return slot


def allowed_module(slot: ModuleTypeSlot, module: Module, mat_type_ids: set[int] | None = None) -> bool:
    """Модуль подходит в строку, если его тип среди выбранных (типы не выбраны — подходит любой).
    Модуль без типа — по типам материалов состава mat_type_ids (как ModulePicker.typeMatch)."""
    type_ids = {t.id for t in slot.material_types}
    if not type_ids:
        return True
    if module.material_type_id is not None:
        return module.material_type_id in type_ids
    return bool(type_ids & (mat_type_ids or set()))


def slot_json(slot: ModuleTypeSlot) -> dict:
    return {
        "id": slot.id,
        "name": slot.name,
        "hidden": bool(slot.hidden),
        "filters": slot.filters.split(",") if slot.filters else [],
        "color": slot.color,
        "join_prev": bool(slot.join_prev),
        "type_ids": [t.id for t in slot.material_types],
        "type_names": [t.name for t in slot.material_types],
    }


def slots_json(slots: list[ModuleTypeSlot]) -> list[dict]:
    """Строки раздела по порядку с блоками объединения: group — id первой строки блока
    (у блока общий фильтр «Ном Ток», остальные фильтры — у каждой строки)."""
    result = []
    head: ModuleTypeSlot | None = None
    for slot in slots:
        if head is None or not slot.join_prev:
            head = slot
        data = slot_json(slot)
        data["group"] = head.id
        result.append(data)
    return result


def order_by_slots(items: list, slots: list[ModuleTypeSlot]) -> list:
    """Общий порядок: сначала обязательные строки по порядку (копии блока строк — сразу за блоком),
    затем остальные модули."""
    pos: dict[int, tuple[int, int]] = {}
    for g, group in enumerate(slot_groups(slots)):
        for i, slot in enumerate(group):
            pos[slot.id] = (g, i)

    def key(it):
        g, i = pos.get(it.slot_id, (0, 0))
        return (it.slot_id not in pos, g, getattr(it, "copy_no", 0) or 0, i, it.id)

    return sorted(items, key=key)


# ── Копии блоков строк в блоке расчёта и в шаблоне ──


def slot_groups(slots: list[ModuleTypeSlot]) -> list[list[ModuleTypeSlot]]:
    """Блоки объединения: подряд идущие строки, где следующая объединена с предыдущей (join_prev)."""
    groups: list[list[ModuleTypeSlot]] = []
    for slot in slots:
        if groups and slot.join_prev:
            groups[-1].append(slot)
        else:
            groups.append([slot])
    return groups


def group_of(slots: list[ModuleTypeSlot], slot_id: int) -> list[ModuleTypeSlot] | None:
    return next((g for g in slot_groups(slots) if any(s.id == slot_id for s in g)), None)


def slot_label(name: str, copy_no: int) -> str:
    """Название строки копии блока: «Выключатель 2» (номер блока: сама строка — 1, копии — 2, 3, ...)."""
    return f"{name} {copy_no + 1}" if copy_no else name


def get_copies(obj) -> dict[int, int]:
    """Количество копий блоков строк блока расчёта / шаблона: {id первой строки блока: количество}."""
    try:
        data = json.loads(obj.slot_copies or "{}")
    except (TypeError, ValueError):
        return {}
    result = {}
    for key, value in data.items() if isinstance(data, dict) else []:
        try:
            if int(value) > 0:
                result[int(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return result


def set_copies(obj, copies: dict[int, int]) -> None:
    clean = {str(k): v for k, v in sorted(copies.items()) if v > 0}
    obj.slot_copies = json.dumps(clean) if clean else None


def effective_copies(slots: list[ModuleTypeSlot], copies: dict[int, int], items: list) -> dict[int, int]:
    """Копии блоков с учётом модулей: копия с модулем показывается, даже если блок строк изменился."""
    result = dict(copies)
    for group in slot_groups(slots):
        ids = {s.id for s in group}
        top = max((it.copy_no for it in items if it.slot_id in ids and it.copy_no), default=0)
        if top > result.get(group[0].id, 0):
            result[group[0].id] = top
    return {k: v for k, v in result.items() if v > 0}


def slot_entries(slots: list[ModuleTypeSlot], copies: dict[int, int], items: list, include_hidden: bool) -> list:
    """Строки блока по порядку: каждый блок строк, за ним его копии.
    [(slot, copy_no, item | None, group)], group — «{id первой строки}:{copy_no}» (рамка блока на странице)."""
    by_key = {(it.slot_id, it.copy_no or 0): it for it in items if it.slot_id is not None}
    copies = effective_copies(slots, copies, items)
    result = []
    for group in slot_groups(slots):
        head = group[0].id
        for n in range(copies.get(head, 0) + 1):
            for slot in group:
                if slot.hidden and not include_hidden:
                    continue
                result.append((slot, n, by_key.get((slot.id, n)), f"{head}:{n}"))
    return result


def _items_model(container):
    """Модель строк блока расчёта (RequestCalcItem) или шаблона (ModuleTypeDefault) и поле связи."""
    if isinstance(container, RequestCalc):
        return RequestCalcItem, RequestCalcItem.calc_id
    return ModuleTypeDefault, ModuleTypeDefault.template_id


async def _group_state(session: AsyncSession, container, slot_id: int):
    """Блок строк, модули его строк в контейнере и количество копий: (group, items, copies) или None."""
    slots = await get_slots(session, container.module_type_id)
    group = group_of(slots, slot_id)
    if group is None:
        return None
    model, field = _items_model(container)
    stmt = select(model).where(field == container.id, model.slot_id.in_([s.id for s in group]))
    items = list((await session.execute(stmt)).scalars().all())
    return group, items, effective_copies(slots, get_copies(container), items)


async def copy_group_in(session: AsyncSession, container, slot_id: int, copy_no: int = 0) -> int | None:
    """Копия блока строк (copy_no — какой экземпляр копировать) в блоке расчёта (RequestCalc) или шаблоне
    (ModuleTypeTemplate) — с модулями, в конец копий этого блока. Строки раздела не меняются.
    Возвращает номер новой копии; None — строка не найдена."""
    state = await _group_state(session, container, slot_id)
    if state is None:
        return None
    group, items, copies = state
    head = group[0].id
    new_no = copies.get(head, 0) + 1
    model, _ = _items_model(container)
    for it in items:
        if (it.copy_no or 0) != copy_no:
            continue
        data = {"slot_id": it.slot_id, "module_id": it.module_id, "quantity": it.quantity, "copy_no": new_no}
        if model is RequestCalcItem:
            session.add(RequestCalcItem(calc_id=container.id, **data))
        else:
            session.add(ModuleTypeDefault(module_type_id=container.module_type_id, template_id=container.id, **data))
    copies[head] = new_no
    set_copies(container, copies)
    await session.flush()
    return new_no


async def delete_group_copy(session: AsyncSession, container, slot_id: int, copy_no: int) -> bool:
    """Удаляет копию блока строк (copy_no ≥ 1) с её модулями; следующие копии сдвигаются на её место."""
    state = await _group_state(session, container, slot_id)
    if state is None or copy_no < 1:
        return False
    group, items, copies = state
    head = group[0].id
    if copy_no > copies.get(head, 0):
        return False
    for it in items:
        if it.copy_no == copy_no:
            await session.delete(it)
    await session.flush()
    for it in sorted(items, key=lambda x: x.copy_no or 0):
        if (it.copy_no or 0) > copy_no:
            it.copy_no -= 1
            await session.flush()
    copies[head] -= 1
    set_copies(container, copies)
    await session.flush()
    return True


async def check_copy_no(session: AsyncSession, container, slot: ModuleTypeSlot, copy_no: int) -> None:
    """Копия блока строк должна существовать в блоке расчёта / шаблоне (ValueError)."""
    if not copy_no:
        return
    state = await _group_state(session, container, slot.id) if container is not None else None
    if state is None or copy_no < 0 or copy_no > state[2].get(state[0][0].id, 0):
        raise ValueError("Копия блока строк не найдена")


# ── Модуль строки: в «по умолчанию» и в блоке расчёта ──


async def _check_module(session: AsyncSession, slot: ModuleTypeSlot, module_id: int | None) -> Module | None:
    if module_id is None:
        return None
    module = await session.get(Module, module_id)
    if not module:
        raise ValueError("Модуль не найден")
    mat_type_ids = None
    if module.material_type_id is None:
        from scr.dbase.crud_modules import get_module_attrs

        mat_type_ids = set((await get_module_attrs(session)).get(module.id, {}).get("mat_type_ids", []))
    if not allowed_module(slot, module, mat_type_ids):
        raise ValueError("Модуль не подходит по типу для этой строки")
    return module


async def set_slot_default(
    session: AsyncSession,
    slot: ModuleTypeSlot,
    module_id: int | None,
    quantity: int,
    template_id: int | None = None,
    copy_no: int = 0,
) -> ModuleTypeDefault | None:
    """Модуль строки в шаблоне (не задан — в основном шаблоне раздела); module_id=None — строка пустая.
    copy_no — строка копии блока строк этого шаблона."""
    from scr.dbase.crud_module_templates import resolve_template

    await _check_module(session, slot, module_id)
    tpl = await resolve_template(session, slot.module_type_id, template_id)
    await check_copy_no(session, tpl, slot, copy_no)
    stmt = select(ModuleTypeDefault).where(
        ModuleTypeDefault.slot_id == slot.id,
        ModuleTypeDefault.template_id == tpl.id,
        ModuleTypeDefault.copy_no == copy_no,
    )
    obj = (await session.execute(stmt)).scalar_one_or_none()
    if module_id is None:
        if obj:
            await session.delete(obj)
            await session.flush()
        return None
    if not obj:
        obj = ModuleTypeDefault(
            module_type_id=slot.module_type_id,
            slot_id=slot.id,
            module_id=module_id,
            template_id=tpl.id,
            copy_no=copy_no,
        )
        session.add(obj)
    obj.module_id = module_id
    obj.quantity = quantity
    await session.flush()
    return obj


async def set_calc_slot(
    session: AsyncSession, calc_id: int, slot: ModuleTypeSlot, module_id: int | None, quantity: int, copy_no: int = 0
) -> RequestCalcItem | None:
    """Модуль строки в блоке расчёта; module_id=None — строка пустая. copy_no — строка копии блока строк."""
    await _check_module(session, slot, module_id)
    await check_copy_no(session, await session.get(RequestCalc, calc_id), slot, copy_no)
    stmt = select(RequestCalcItem).where(
        RequestCalcItem.calc_id == calc_id, RequestCalcItem.slot_id == slot.id, RequestCalcItem.copy_no == copy_no
    )
    obj = (await session.execute(stmt)).scalar_one_or_none()
    if module_id is None:
        if obj:
            await session.delete(obj)
            await session.flush()
        return None
    if not obj:
        obj = RequestCalcItem(calc_id=calc_id, slot_id=slot.id, module_id=module_id, copy_no=copy_no)
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
        if d.template_id in template_ids and not d.copy_no
    }

    calcs_stmt = (
        select(RequestCalc)
        .where(RequestCalc.request_id == request_id, RequestCalc.module_type_id.in_(hidden_by_type))
        .options(selectinload(RequestCalc.items), selectinload(RequestCalc.module_type))
    )
    changed_calcs: list[RequestCalc] = []
    for calc in (await session.execute(calcs_stmt)).scalars().all():
        # Копии блоков строк — данные блока расчёта, с шаблоном не синхронизируются
        items = {it.slot_id: it for it in calc.items if it.slot_id is not None and not it.copy_no}
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
        crud_module_types.apply_fot_rule(calc, prices, await crud_module_types.get_fot_rule(session, calc.module_type))
        total = crud_module_types.calc_base_cost(calc, prices, works=works)
        calc.total_cost = round(total, 2)
        calc.final_price = round(total * (1 + float(calc.profitability_percent or 0) / 100), 2)
    await session.flush()
    for type_id in {c.module_type_id for c in changed_calcs}:
        await crud_module_types.recalc_section_cost(session, request_id, type_id)
    return True
