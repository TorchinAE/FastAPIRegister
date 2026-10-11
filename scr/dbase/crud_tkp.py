"""Сводная таблица ТКП: разделы расчёта, доставка, услуги."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase import crud_modules, crud_settings
from scr.dbase.crud_module_types import MULTI_BLOCK_SECTIONS
from scr.dbase.models import Delivery, Material, ModuleType, Request, RequestCalc, RequestCalcItem, ServiceCalc

SERVICE_SECTIONS = [("chief-engineer", "Шеф-инженер"), ("smr", "СМР"), ("pnr", "ПНР")]


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
        if mt.slug in MULTI_BLOCK_SECTIONS:
            qty = sum(c.quantity or 0 for c in type_calcs)
        else:
            qty = request_quantities.get(mt.slug, 0) or 0
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

    for calc in calcs:
        block_qty = calc.quantity if calc.quantity is not None else 1
        for item in calc.items:
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
