"""Сводная таблица ТКП: разделы расчёта, доставка, услуги."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase import crud_modules, crud_settings
from scr.dbase.crud_module_types import MULTI_BLOCK_SECTIONS, SECTION_COST_FIELDS, WORKS_SECTIONS
from scr.dbase.models import Delivery, Material, ModuleType, Request, RequestCalc, RequestCalcItem, ServiceCalc

SERVICE_SECTIONS = [("chief-engineer", "Шеф-инженер"), ("smr", "СМР"), ("pnr", "ПНР")]
# Порядок разделов в сводной и комплектации ТКП — как на странице расчёта
SECTION_ORDER = {slug: i for i, slug in enumerate(SECTION_COST_FIELDS)}
# Разделы, где количество — сумма количеств блоков (у Корпусов один блок, но со своим количеством)
BLOCK_QTY_SECTIONS = MULTI_BLOCK_SECTIONS | {"corpusa"}


def _block_qty(calc: RequestCalc) -> int:
    return calc.quantity if calc.quantity is not None else 1


def _row(slug: str, name: str, qty, comp, fot, overhead, cost, final) -> dict:
    return {
        "slug": slug,
        "name": name,
        "quantity": qty,
        "comp": comp,
        "fot": fot,
        "overhead": overhead,
        "cost": cost,
        "profit_percent": (final / cost - 1) * 100 if cost else 0.0,
        "profit": final - cost,
        "final": final,
    }


async def build_tkp_summary(session: AsyncSession, req: Request) -> dict:
    """Строки по разделам и итоги. Стоимости блоков умножаются на их количество."""
    nds_val = await crud_settings.get_setting(session, "nds_percent")
    nds_percent = float(nds_val) if nds_val else 20.0

    stmt = (
        select(RequestCalc)
        .where(RequestCalc.request_id == req.id)
        .options(selectinload(RequestCalc.module_type))
        .order_by(RequestCalc.module_type_id, RequestCalc.id)
    )
    calcs = list((await session.execute(stmt)).scalars().all())

    # Кол-во из заявки для разделов с одним блоком
    request_quantities = {"ktp": req.ktp, "pku": req.pku, "pus": req.pus}

    rows: list[dict] = []
    by_type: dict[int, list[RequestCalc]] = {}
    types: dict[int, ModuleType] = {}
    for calc in calcs:
        by_type.setdefault(calc.module_type_id, []).append(calc)
        types[calc.module_type_id] = calc.module_type

    for type_id, type_calcs in by_type.items():
        mt = types[type_id]
        comp = fot = overhead = cost = final = 0.0
        for c in type_calcs:
            q = c.quantity if c.quantity is not None else 1
            c_fot, c_overhead, c_cost = float(c.fot or 0), float(c.overhead or 0), float(c.total_cost or 0)
            fot += c_fot * q
            overhead += c_overhead * q
            cost += c_cost * q
            comp += max(c_cost - c_fot - c_overhead, 0) * q
            final += float(c.final_price or 0) * q
        if mt.slug in BLOCK_QTY_SECTIONS:
            qty = sum(c.quantity or 0 for c in type_calcs)
        else:
            # КТП, ПКУ, ПУС — из заявки; работы и прочие — 1, если есть стоимость
            qty = request_quantities.get(mt.slug, 0) or (1 if final > 0 else 0)
        rows.append(_row(mt.slug, mt.name, qty, comp, fot, overhead, cost, final))

    delivery = (await session.execute(select(Delivery).where(Delivery.request_id == req.id))).scalars().first()
    if delivery and float(delivery.final_price or 0) > 0:
        d_cost = float(delivery.cost_per_truck or 0) * (delivery.trucks_count or 0)
        rows.append(
            _row("delivery", "Доставка", delivery.trucks_count or 0, 0.0, 0.0, 0.0, d_cost, float(delivery.final_price))
        )

    # Старые расчёты услуг — только если по разделу нет нового расчёта
    calc_slugs = {r["slug"] for r in rows}
    for section, label in SERVICE_SECTIONS:
        if section in calc_slugs:
            continue
        sc_stmt = select(ServiceCalc).where(ServiceCalc.request_id == req.id, ServiceCalc.section == section)
        sc = (await session.execute(sc_stmt)).scalars().first()
        if sc and float(sc.final_price or 0) > 0:
            base = float(sc.base_cost or 0)
            rows.append(_row(section, label, sc.quantity or 1, 0.0, 0.0, 0.0, base, float(sc.final_price)))

    rows.sort(key=lambda r: SECTION_ORDER.get(r["slug"], len(SECTION_ORDER)))
    totals = {key: sum(r[key] for r in rows) for key in ("comp", "fot", "overhead", "cost", "final")}
    totals["final_nds"] = totals["final"] * (1 + nds_percent / 100)
    # Средняя рентабельность — взвешенная по себестоимости: прибыль / себестоимость
    totals["profit"] = totals["final"] - totals["cost"]
    totals["profit_percent"] = totals["profit"] / totals["cost"] * 100 if totals["cost"] else 0.0
    for r in rows:
        r["final_nds"] = r["final"] * (1 + nds_percent / 100)
    return {"rows": rows, "totals": totals, "nds_percent": nds_percent}


async def build_kit(session: AsyncSession, req: Request) -> dict:
    """Комплектация ТКП по всем разделам.

    modules — модули по разделам (кол-во = кол-во в блоке × кол-во блоков),
    materials — все материалы с раскрытием подмодулей, сведённые по материалу.
    """
    stmt = (
        select(RequestCalc)
        .where(RequestCalc.request_id == req.id)
        .options(
            selectinload(RequestCalc.module_type),
            selectinload(RequestCalc.items).selectinload(RequestCalcItem.module),
        )
        .order_by(RequestCalc.module_type_id, RequestCalc.id)
    )
    calcs = list((await session.execute(stmt)).scalars().all())
    prices = await crud_modules.get_module_prices(session)
    tree, _ = await crud_modules.load_tree(session)

    modules: dict[tuple[str, int], dict] = {}
    material_qty: dict[int, float] = {}

    def expand(module_id: int, mult: float, stack: frozenset) -> None:
        if module_id in stack:
            return
        for material_id, sub_module_id, qty in tree.get(module_id, []):
            if material_id is not None:
                material_qty[material_id] = material_qty.get(material_id, 0) + qty * mult
            elif sub_module_id is not None:
                expand(sub_module_id, qty * mult, stack | {module_id})

    from scr.dbase.crud_module_slots import get_slots, order_by_slots

    slots_by_type = {t: await get_slots(session, t) for t in {c.module_type_id for c in calcs}}
    for calc in calcs:
        block_qty = calc.quantity if calc.quantity is not None else 1
        # Общий порядок: обязательные строки (и скрытые) по порядку, затем остальные модули
        for item in order_by_slots(calc.items, slots_by_type[calc.module_type_id]):
            qty = item.quantity * block_qty
            if not qty:
                continue
            key = (calc.module_type.name, item.module_id)
            row = modules.setdefault(
                key,
                {
                    "section": calc.module_type.name,
                    "module_id": item.module_id,
                    "name": item.module.name if item.module else f"Модуль {item.module_id}",
                    "quantity": 0,
                    "price": prices.get(item.module_id, 0.0),
                },
            )
            row["quantity"] += qty
            expand(item.module_id, qty, frozenset())

    module_rows = list(modules.values())
    for row in module_rows:
        row["sum"] = row["price"] * row["quantity"]

    material_rows: list[dict] = []
    if material_qty:
        mat_stmt = select(Material).where(Material.id.in_(material_qty)).options(selectinload(Material.type))
        for mat in (await session.execute(mat_stmt)).scalars().all():
            qty = material_qty[mat.id]
            price = float(mat.price or 0)
            material_rows.append(
                {
                    "id": mat.id,
                    "code_1c": mat.code_1c or "",
                    "type": mat.type.name if mat.type else "",
                    "name": mat.name,
                    "nom_tok": mat.nom_tok or 0,
                    "price": price,
                    "quantity": qty,
                    "sum": price * qty,
                }
            )
        material_rows.sort(key=lambda r: (r["type"], r["name"]))
    return {"modules": module_rows, "materials": material_rows}


def kit_line(purpose: str | None, quantity: int, name: str) -> str:
    """Строка модуля в комплектации: «Назначение: 3хНазвание» (1 шт. — без «1х»), без назначения — «1хНазвание»."""
    if purpose:
        return f"{purpose}: {f'{quantity}х' if quantity > 1 else ''}{name}"
    return f"{quantity}х{name}"


async def build_tkp_kit(session: AsyncSession, req: Request) -> list[dict]:
    """Комплектация для ТКП: разделы по порядку, в них блоки с составом, количеством и ценой.

    Блок: title — «{название блока}-{назначение}», lines — модули блока по порядку строк (скрытые строки
    не выводятся, но входят в цену), quantity — количество блоков, price — общая стоимость блока без НДС.
    Разделы работ и доставка — одной строкой, количество 1 при ненулевой стоимости.
    """
    from scr.dbase.crud_module_slots import get_slots, order_by_slots

    stmt = (
        select(RequestCalc)
        .where(RequestCalc.request_id == req.id)
        .options(
            selectinload(RequestCalc.module_type),
            selectinload(RequestCalc.items).selectinload(RequestCalcItem.module),
        )
        .order_by(RequestCalc.module_type_id, RequestCalc.id)
    )
    calcs = list((await session.execute(stmt)).scalars().all())
    by_type: dict[int, list[RequestCalc]] = {}
    for calc in calcs:
        by_type.setdefault(calc.module_type_id, []).append(calc)

    sections: list[dict] = []
    for type_calcs in by_type.values():
        mt = type_calcs[0].module_type
        if mt.slug in WORKS_SECTIONS:
            price = sum(float(c.final_price or 0) * _block_qty(c) for c in type_calcs)
            if price > 0:
                block = {"title": mt.name, "lines": [], "quantity": 1, "price": price, "sum": price}
                sections.append({"slug": mt.slug, "name": mt.name, "header": False, "blocks": [block]})
            continue
        slots = {s.id: s for s in await get_slots(session, mt.id)}
        blocks = []
        for calc in type_calcs:
            qty = _block_qty(calc)
            price = float(calc.final_price or 0)
            if not qty or (not calc.items and not price):
                continue
            title = calc.name or mt.name
            if calc.purpose:
                title += f"-{calc.purpose}"
            lines = []
            for item in order_by_slots(calc.items, list(slots.values())):
                slot = slots.get(item.slot_id)
                if slot is not None and slot.hidden or not item.quantity:
                    continue
                name = item.module.name if item.module else f"Модуль {item.module_id}"
                lines.append(kit_line(slot.purpose if slot else None, item.quantity, name))
            blocks.append({"title": title, "lines": lines, "quantity": qty, "price": price, "sum": price * qty})
        if blocks:
            # Заголовок «в составе» — у разделов из нескольких блоков (КСО, КРУ, ЩО)
            header = mt.slug in MULTI_BLOCK_SECTIONS
            sections.append({"slug": mt.slug, "name": mt.name, "header": header, "blocks": blocks})

    delivery = (await session.execute(select(Delivery).where(Delivery.request_id == req.id))).scalars().first()
    if delivery and float(delivery.final_price or 0) > 0:
        price = float(delivery.final_price)
        block = {"title": "Доставка", "lines": [], "quantity": 1, "price": price, "sum": price}
        sections.append({"slug": "delivery", "name": "Доставка", "header": False, "blocks": [block]})
    # Старые расчёты услуг — как в сводной: только если по разделу нет нового расчёта
    present = {s["slug"] for s in sections} | {c.module_type.slug for c in calcs}
    for section, label in SERVICE_SECTIONS:
        if section in present:
            continue
        sc_stmt = select(ServiceCalc).where(ServiceCalc.request_id == req.id, ServiceCalc.section == section)
        sc = (await session.execute(sc_stmt)).scalars().first()
        if sc and float(sc.final_price or 0) > 0:
            price = float(sc.final_price)
            block = {"title": label, "lines": [], "quantity": 1, "price": price, "sum": price}
            sections.append({"slug": section, "name": label, "header": False, "blocks": [block]})
    sections.sort(key=lambda s: SECTION_ORDER.get(s["slug"], len(SECTION_ORDER)))
    return sections


async def build_calc_materials(session: AsyncSession, calcs: list[RequestCalc]) -> tuple[list[dict], list[dict]]:
    """Материалы блоков расчёта одного раздела (подмодули раскрыты).

    Возвращает (материалы [{id, name, price, date, type}], по блокам [{material_id: кол-во на один блок}]).
    """
    tree, _ = await crud_modules.load_tree(session)

    def expand(module_id: int, mult: float, acc: dict[int, float], stack: frozenset) -> None:
        if module_id in stack:
            return
        for material_id, sub_module_id, qty in tree.get(module_id, []):
            if material_id is not None:
                acc[material_id] = acc.get(material_id, 0) + qty * mult
            elif sub_module_id is not None:
                expand(sub_module_id, qty * mult, acc, stack | {module_id})

    per_calc: list[dict[int, float]] = []
    for calc in calcs:
        acc: dict[int, float] = {}
        for item in calc.items:
            if item.quantity:
                expand(item.module_id, item.quantity, acc, frozenset())
        per_calc.append(acc)

    ids = {mid for acc in per_calc for mid in acc}
    materials: list[dict] = []
    if ids:
        mat_stmt = select(Material).where(Material.id.in_(ids)).options(selectinload(Material.type))
        for mat in (await session.execute(mat_stmt)).scalars().all():
            materials.append(
                {
                    "id": mat.id,
                    "name": mat.name,
                    "price": float(mat.price or 0),
                    "date": mat.date,
                    "type": mat.type.name if mat.type else "",
                }
            )
        materials.sort(key=lambda r: (r["type"], r["name"]))
    return materials, per_calc
