from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase.models import InvoiceItem, ModuleType, ModuleTypeDefault, PayrollItem, RequestCalc, RequestCalcItem
from scr.dbase.schemas.schemas import (
    ModuleTypeCreateSchema,
    ModuleTypeDefaultCreateSchema,
    RequestCalcItemCreateSchema,
    RequestCalcItemUpdateSchema,
    RequestCalcUpdateSchema,
)

# ── ModuleType ──


async def get_module_types(session: AsyncSession) -> list[ModuleType]:
    stmt = (
        select(ModuleType)
        .options(selectinload(ModuleType.fot_item), selectinload(ModuleType.overhead_item))
        .order_by(ModuleType.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_module_type_by_id(session: AsyncSession, type_id: int) -> ModuleType | None:
    stmt = (
        select(ModuleType)
        .where(ModuleType.id == type_id)
        .options(selectinload(ModuleType.fot_item), selectinload(ModuleType.overhead_item))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_module_type_by_slug(session: AsyncSession, slug: str) -> ModuleType | None:
    stmt = (
        select(ModuleType)
        .where(ModuleType.slug == slug)
        .options(selectinload(ModuleType.fot_item), selectinload(ModuleType.overhead_item))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_module_type(
    session: AsyncSession, data: ModuleTypeCreateSchema, created_by: str | None = None
) -> ModuleType:
    existing = await get_module_type_by_slug(session, data.slug)
    if existing:
        return existing
    by_name = (await session.execute(select(ModuleType).where(ModuleType.name == data.name))).scalar_one_or_none()
    if by_name:
        return by_name
    obj = ModuleType(**data.model_dump())
    obj.created_by = created_by
    session.add(obj)
    await session.flush()
    return obj


async def delete_module_type(session: AsyncSession, type_id: int) -> ModuleType | None:
    obj = await get_module_type_by_id(session, type_id)
    if obj:
        await session.delete(obj)
        await session.flush()
    return obj


async def get_or_create_fot_item(session: AsyncSession, type_name: str) -> PayrollItem:
    name = f"ФОТ_{type_name}"
    stmt = select(PayrollItem).where(PayrollItem.name == name)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if item:
        return item
    item = PayrollItem(name=name, cost=0)
    session.add(item)
    await session.flush()
    return item


async def get_or_create_overhead_item(session: AsyncSession, type_name: str) -> InvoiceItem:
    name = f"Накладные_{type_name}"
    stmt = select(InvoiceItem).where(InvoiceItem.name == name)
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()
    if item:
        return item
    item = InvoiceItem(name=name, cost=0)
    session.add(item)
    await session.flush()
    return item


# ── ModuleTypeDefault ──


async def get_defaults(session: AsyncSession, module_type_id: int) -> list[ModuleTypeDefault]:
    stmt = (
        select(ModuleTypeDefault)
        .where(ModuleTypeDefault.module_type_id == module_type_id)
        .options(selectinload(ModuleTypeDefault.module))
        .order_by(ModuleTypeDefault.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def add_default(session: AsyncSession, data: ModuleTypeDefaultCreateSchema) -> ModuleTypeDefault:
    # Обычный модуль по умолчанию (не обязательная строка) уже есть — увеличиваем количество
    stmt = select(ModuleTypeDefault).where(
        ModuleTypeDefault.module_type_id == data.module_type_id,
        ModuleTypeDefault.module_id == data.module_id,
        ModuleTypeDefault.slot_id.is_(None),
    )
    existing = (await session.execute(stmt)).scalars().first()
    if existing:
        existing.quantity += data.quantity
        await session.flush()
        return existing
    obj = ModuleTypeDefault(**data.model_dump())
    session.add(obj)
    await session.flush()
    return obj


async def delete_default(session: AsyncSession, default_id: int) -> ModuleTypeDefault | None:
    obj = await session.get(ModuleTypeDefault, default_id)
    if obj:
        await session.delete(obj)
        await session.flush()
    return obj


# ── RequestCalc ──

# Разделы расчёта → поле стоимости в Request
SECTION_COST_FIELDS = {
    "corpusa": "corpusa_cost",
    "kso": "kso_cost",
    "kru": "kru_cost",
    "sho": "sho_cost",
    "ktp": "ktp_cost",
    "pku": "pku_cost",
    "pus": "pus_cost",
    "delivery": "delivery_cost",
    "chief-engineer": "chief_engineer_cost",
    "smr": "smr_cost",
    "pnr": "pnr_cost",
}
# Разделы, где можно добавлять несколько блоков расчёта
MULTI_BLOCK_SECTIONS = {"kso", "kru", "sho"}
# Разделы работ: вместо модулей — себестоимость работ
WORKS_SECTIONS = {"chief-engineer", "smr", "pnr"}


def _calc_options():
    return selectinload(RequestCalc.items).selectinload(RequestCalcItem.module)


async def get_calcs(session: AsyncSession, request_id: int, module_type_id: int) -> list[RequestCalc]:
    stmt = (
        select(RequestCalc)
        .where(RequestCalc.request_id == request_id, RequestCalc.module_type_id == module_type_id)
        .options(_calc_options())
        .order_by(RequestCalc.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_calc(session: AsyncSession, request_id: int, module_type_id: int) -> RequestCalc:
    """Новый блок расчёта со значениями по умолчанию: ФОТ/Накладные из справочников, модули по умолчанию."""
    mod_type = await get_module_type_by_id(session, module_type_id)
    calc = RequestCalc(
        request_id=request_id,
        module_type_id=module_type_id,
        fot=float(mod_type.fot_item.cost) if mod_type and mod_type.fot_item else 0,
        overhead=float(mod_type.overhead_item.cost) if mod_type and mod_type.overhead_item else 0,
        quantity=1,
        works_cost=0,
    )
    session.add(calc)
    await session.flush()

    if mod_type and mod_type.slug not in WORKS_SECTIONS:
        # Состав нового блока — модули обязательных строк раздела
        for d in await get_defaults(session, module_type_id):
            if d.slot_id is None:
                continue
            session.add(RequestCalcItem(calc_id=calc.id, module_id=d.module_id, quantity=d.quantity, slot_id=d.slot_id))
        await session.flush()

    calc = await get_calc_by_id(session, calc.id)
    # Итоги блока сразу, чтобы стоимость раздела учитывала новый блок без нажатия «Сохранить»
    from scr.dbase.crud_modules import get_module_prices

    prices = await get_module_prices(session)
    profit = await default_profitability(session, request_id)
    total = calc_base_cost(calc, prices, works=bool(mod_type and mod_type.slug in WORKS_SECTIONS))
    calc.profitability_percent = profit
    calc.total_cost = round(total, 2)
    calc.final_price = round(total * (1 + profit / 100), 2)
    await session.flush()
    return calc


async def default_profitability(session: AsyncSession, request_id: int) -> float:
    """Рентабельность по умолчанию — из организации заявки (15%, если не задана)."""
    from scr.dbase.models import Organization, Request

    stmt = select(Organization.profitability).join(Request, Request.company_id == Organization.id)
    value = (await session.execute(stmt.where(Request.id == request_id))).scalar_one_or_none()
    return float(value) if value else 15.0


def calc_base_cost(calc: RequestCalc, prices: dict[int, float], works: bool) -> float:
    """Себестоимость блока: модули (или себестоимость работ) + ФОТ + Накладные."""
    if works:
        base = float(calc.works_cost or 0)
    else:
        base = sum(prices.get(it.module_id, 0.0) * it.quantity for it in calc.items)
    return base + float(calc.fot or 0) + float(calc.overhead or 0)


def _item_data(it: RequestCalcItem, prices: dict[int, float]) -> dict:
    return {
        "id": it.id,
        "module_id": it.module_id,
        "module_name": it.module.name if it.module else "?",
        "quantity": it.quantity,
        "module_price": prices.get(it.module_id, 0.0),
    }


def calc_block_data(calc: RequestCalc, prices: dict[int, float], default_profit: float, slots: list) -> dict:
    """Данные блока расчёта для страницы.

    slots — обязательные строки раздела: видимые выводятся строками с выбором модуля,
    скрытые не выводятся, их сумма идёт в hidden_total. items — модули, добавленные вручную.
    """
    profit = float(calc.profitability_percent or 0)
    by_slot = {it.slot_id: it for it in calc.items if it.slot_id is not None}
    known = {s.id for s in slots}
    hidden_total = sum(
        prices.get(by_slot[s.id].module_id, 0.0) * by_slot[s.id].quantity for s in slots if s.hidden and s.id in by_slot
    )
    return {
        "id": calc.id,
        "fot": float(calc.fot or 0),
        "overhead": float(calc.overhead or 0),
        "profitability_percent": profit if profit > 0 else default_profit,
        "quantity": calc.quantity if calc.quantity is not None else 1,
        "works_cost": float(calc.works_cost or 0),
        "total_cost": float(calc.total_cost or 0),
        "final_price": float(calc.final_price or 0),
        "slots": [
            {"slot_id": s.id, "item": _item_data(by_slot[s.id], prices) if s.id in by_slot else None}
            for s in slots
            if not s.hidden
        ],
        "hidden_total": hidden_total,
        "items": [_item_data(it, prices) for it in calc.items if it.slot_id not in known],
    }


async def get_or_create_calcs(session: AsyncSession, request_id: int, module_type_id: int) -> list[RequestCalc]:
    calcs = await get_calcs(session, request_id, module_type_id)
    if not calcs:
        return [await create_calc(session, request_id, module_type_id)]

    # Refresh fot/overhead from linked items if calc values are still 0
    mod_type = await get_module_type_by_id(session, module_type_id)
    for calc in calcs:
        if mod_type and mod_type.fot_item and float(calc.fot) == 0 and float(mod_type.fot_item.cost) > 0:
            calc.fot = float(mod_type.fot_item.cost)
        if mod_type and mod_type.overhead_item and float(calc.overhead) == 0 and float(mod_type.overhead_item.cost) > 0:
            calc.overhead = float(mod_type.overhead_item.cost)
    return calcs


async def get_or_create_calc(session: AsyncSession, request_id: int, module_type_id: int) -> RequestCalc:
    return (await get_or_create_calcs(session, request_id, module_type_id))[0]


async def recalc_section_cost(session: AsyncSession, request_id: int, module_type_id: int) -> float:
    """Стоимость раздела в ТКП = сумма (общая стоимость блока × количество)."""
    from scr.dbase.models import Request

    mod_type = await session.get(ModuleType, module_type_id)
    req = await session.get(Request, request_id)
    if not mod_type or not req:
        return 0.0
    calcs = await get_calcs(session, request_id, module_type_id)
    total = sum(float(c.final_price or 0) * (c.quantity or 0) for c in calcs)
    field = SECTION_COST_FIELDS.get(mod_type.slug)
    if field:
        setattr(req, field, round(total, 2))
        await session.flush()
    return total


async def delete_calc(session: AsyncSession, calc_id: int) -> RequestCalc | None:
    calc = await session.get(RequestCalc, calc_id)
    if calc:
        await session.delete(calc)
        await session.flush()
    return calc


async def get_calc_by_id(session: AsyncSession, calc_id: int) -> RequestCalc | None:
    stmt = select(RequestCalc).where(RequestCalc.id == calc_id).options(_calc_options())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_calc(session: AsyncSession, data: RequestCalcUpdateSchema) -> RequestCalc | None:
    calc = await session.get(RequestCalc, data.id)
    if not calc:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        if field != "id" and hasattr(calc, field):
            setattr(calc, field, value)
    await session.flush()
    return calc


# ── RequestCalcItem ──


async def add_calc_item(session: AsyncSession, data: RequestCalcItemCreateSchema) -> RequestCalcItem:
    # Модуль уже добавлен в блок вручную (не обязательной строкой) — увеличиваем количество
    stmt = select(RequestCalcItem).where(
        RequestCalcItem.calc_id == data.calc_id,
        RequestCalcItem.module_id == data.module_id,
        RequestCalcItem.slot_id.is_(None),
    )
    existing = (await session.execute(stmt)).scalars().first()
    if existing:
        existing.quantity += data.quantity
        await session.flush()
        return existing
    obj = RequestCalcItem(**data.model_dump())
    session.add(obj)
    await session.flush()
    return obj


async def update_calc_item(session: AsyncSession, data: RequestCalcItemUpdateSchema) -> RequestCalcItem | None:
    obj = await session.get(RequestCalcItem, data.id)
    if not obj:
        return None
    obj.quantity = data.quantity
    await session.flush()
    return obj


async def delete_calc_item(session: AsyncSession, item_id: int) -> RequestCalcItem | None:
    obj = await session.get(RequestCalcItem, item_id)
    if obj:
        await session.delete(obj)
        await session.flush()
    return obj
