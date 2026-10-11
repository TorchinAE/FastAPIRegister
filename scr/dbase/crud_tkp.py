"""Сводная таблица ТКП: разделы расчёта, доставка, услуги."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase import crud_settings
from scr.dbase.crud_module_types import MULTI_BLOCK_SECTIONS
from scr.dbase.models import Delivery, ModuleType, Request, RequestCalc, ServiceCalc

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
    for r in rows:
        r["final_nds"] = r["final"] * (1 + nds_percent / 100)
    return {"rows": rows, "totals": totals, "nds_percent": nds_percent}
