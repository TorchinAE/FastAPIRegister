"""Расчёт КСО ТКП ↔ файл КСО204-ткп{№ ТКП}.xlsx в папке ТКП; варианты расчёта."""

import os
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.constants import DEFAULT_K_FOT, DEFAULT_K_NAKL, KSO_PURPOSES, SETTING_K_FOT, SETTING_K_NAKL
from scr.dbase import crud_module_slots, crud_module_types, crud_modules, crud_settings
from scr.dbase.models import Module, Request, RequestCalc, RequestCalcItem
from scr.dbase.schemas.schemas import RequestCalcItemCreateSchema
from scr.utils import kso204
from scr.utils.kso204 import KsoBlock, KsoHeader

KSO_SLUG = "kso"
# Папка ТКП, если на сервере не задан adres_server
LOCAL_TKP_ROOT = Path(__file__).resolve().parent.parent.parent / "tkp_files"


def tkp_folder_path(adres_server: str, req: Request) -> str | None:
    """Папка ТКП на сервере: {adres_server}/01_ТКП/01_ТКП_{год}/{slug организации}/{id}_{организация}."""
    if not adres_server or not req.company:
        return None
    year = req.request_date.year if req.request_date else 2025
    slug = req.company.server_address_slug or "default"
    org_name = (
        (req.company.name or "Unknown")
        .replace(" ", "_")
        .replace('"', "")
        .replace("'", "")
        .replace("/", "_")
        .replace("\\", "_")
    )
    return os.path.join(adres_server, "01_ТКП", f"01_ТКП_{year}", slug, f"{req.id}_{org_name}")


async def get_tkp_folder(session: AsyncSession, req: Request) -> Path:
    """Папка для файлов расчёта ТКП (создаётся). Без адреса сервера или при ошибке — локальная tkp_files/{id}."""
    adres_server = await crud_settings.get_setting(session, "adres_server") or ""
    path = tkp_folder_path(adres_server, req)
    if path:
        try:
            os.makedirs(path, exist_ok=True)
            return Path(path)
        except OSError:
            pass
    folder = LOCAL_TKP_ROOT / str(req.id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


async def _kso_type(session: AsyncSession):
    mt = await crud_module_types.get_module_type_by_slug(session, KSO_SLUG)
    if not mt:
        raise ValueError("Раздел расчёта КСО не найден")
    return mt


async def _setting_float(session: AsyncSession, key: str, default: float) -> float:
    value = await crud_settings.get_setting(session, key)
    try:
        return float(str(value).replace(",", ".")) if value else default
    except ValueError:
        return default


def _header(req: Request) -> KsoHeader:
    cp = req.counterparty
    return KsoHeader(
        tkp_num=req.tkp_num or str(req.id),
        issue_date=kso204.to_date(req.issue_date) or date.today(),
        object_name=req.description or "",
        company=req.company.name if req.company else "",
        contact=cp.name if cp else "",
        phone=(cp.phone or "") if cp else "",
    )


async def build_request_kso204(session: AsyncSession, req: Request) -> tuple[bytes, list[str]]:
    """Книга КСО204 по расчёту КСО заявки: (xlsx, предупреждения)."""
    mt = await _kso_type(session)
    await crud_module_slots.sync_hidden_slots(session, req.id)
    calcs = await crud_module_types.get_calcs(session, req.id, mt.id)
    slots = await crud_module_slots.get_slots(session, mt.id)
    slot_by_id = {s.id: s for s in slots}
    blocks = []
    for calc in calcs:
        block = KsoBlock(
            qty_1sh=calc.qty_1sh or 0,
            qty_2sh=calc.qty_2sh or 0,
            profit_percent=float(calc.profitability_percent or 0),
            fot=float(calc.fot or 0),
            overhead=float(calc.overhead or 0),
            purpose=calc.purpose or "",
        )
        for it in crud_module_slots.order_by_slots(list(calc.items), slots):
            name = it.module.name if it.module else ""
            slot = slot_by_id.get(it.slot_id)
            if not name:
                continue
            if slot is None:
                block.extras.append((name, it.quantity))
            elif slot.hidden and kso204.slot_row(slot.name) is None:
                # Скрытая строка восстанавливается из «по умолчанию» — в «Дополнительно» не пишем
                continue
            else:
                block.slots.append((slot.name, name, it.quantity))
        blocks.append(block)
    header = _header(req)
    header.bus_current = max((it.module.nom_tok or 0 for c in calcs for it in c.items if it.module), default=0) or None
    header.k_fot = await _setting_float(session, SETTING_K_FOT, DEFAULT_K_FOT)
    header.k_nakl = await _setting_float(session, SETTING_K_NAKL, DEFAULT_K_NAKL)
    return kso204.build_kso204(header, blocks)


async def save_request_kso204(session: AsyncSession, req: Request) -> tuple[Path, list[str]]:
    data, warnings = await build_request_kso204(session, req)
    path = await get_tkp_folder(session, req) / kso204.kso204_filename(req.tkp_num or str(req.id))
    path.write_bytes(data)
    return path, warnings


async def load_request_kso204(session: AsyncSession, req: Request, data: bytes) -> list[str]:
    """Заменяет расчёт КСО заявки блоками из файла КСО204. Возвращает предупреждения."""
    mt = await _kso_type(session)
    parsed = kso204.parse_kso204(data)
    slots = [s for s in await crud_module_slots.get_slots(session, mt.id) if not s.hidden]
    modules = {m.name.strip().lower(): m for m in (await session.execute(select(Module))).scalars().all()}
    warnings: list[str] = []

    def find_module(name: str, block_no: int) -> Module | None:
        mod = modules.get(name.strip().lower())
        if not mod:
            warnings.append(f"Блок {block_no}: модуль «{name}» не найден в базе")
        return mod

    for calc in await crud_module_types.get_calcs(session, req.id, mt.id):
        await session.delete(calc)
    await session.flush()

    default_profit = await crud_module_types.default_profitability(session, req.id)
    for pb in parsed:
        calc = await crud_module_types.create_calc(session, req.id, mt.id)
        free_rows = dict(pb.rows)
        extras: list[tuple[Module, int]] = []
        for name, qty in pb.extras:
            mod = find_module(name, pb.index)
            if mod:
                extras.append((mod, qty))

        # Обязательные строки: модуль из строки листа с тем же названием
        empty_slots = []
        for slot in slots:
            row = kso204.slot_row(slot.name)
            name = free_rows.pop(row, "") if row else ""
            mod = find_module(name, pb.index) if name else None
            qty = pb.tt_qty if row == kso204.ROW_TT else 1
            try:
                await crud_module_slots.set_calc_slot(session, calc.id, slot, mod.id if mod else None, qty)
            except ValueError:
                warnings.append(f"Блок {pb.index}: «{mod.name}» не подходит по типу в строку «{slot.name}»")
                await crud_module_slots.set_calc_slot(session, calc.id, slot, None, 1)
                extras.append((mod, qty))
                mod = None
            if mod is None:
                empty_slots.append(slot)

        # Пустые строки с заданными типами — модуль подходящего типа из «Дополнительно»
        for slot in empty_slots:
            type_ids = {t.id for t in slot.material_types}
            match = next((e for e in extras if type_ids and e[0].material_type_id in type_ids), None)
            if match:
                extras.remove(match)
                await crud_module_slots.set_calc_slot(session, calc.id, slot, match[0].id, match[1])

        # Модули строк листа без обязательной строки в расчёте и «Дополнительно» — обычными модулями
        for name in free_rows.values():
            mod = find_module(name, pb.index)
            if mod:
                extras.append((mod, 1))
        for mod, qty in extras:
            await crud_module_types.add_calc_item(
                session, RequestCalcItemCreateSchema(calc_id=calc.id, module_id=mod.id, quantity=qty)
            )

        calc.fot = pb.fot
        calc.overhead = pb.overhead
        calc.profitability_percent = pb.profit_percent if pb.profit_percent is not None else default_profit
        calc.qty_1sh, calc.qty_2sh = pb.qty_1sh, pb.qty_2sh
        calc.purpose = pb.purpose if pb.purpose in KSO_PURPOSES else None
        calc.quantity = pb.qty_1sh + pb.qty_2sh
        await session.flush()

    if not parsed:
        # Пустой файл — один блок по умолчанию, как при первом открытии расчёта
        await crud_module_types.create_calc(session, req.id, mt.id)
    await session.flush()
    # Строки блоков добавлялись мимо загруженных коллекций — перечитываем блоки с их составом
    stmt = (
        select(RequestCalc)
        .where(RequestCalc.request_id == req.id, RequestCalc.module_type_id == mt.id)
        .options(selectinload(RequestCalc.items).selectinload(RequestCalcItem.module))
        .execution_options(populate_existing=True)
    )
    prices = await crud_modules.get_module_prices(session)
    for calc in (await session.execute(stmt)).scalars().all():
        total = crud_module_types.calc_base_cost(calc, prices, works=False)
        calc.total_cost = round(total, 2)
        calc.final_price = round(total * (1 + float(calc.profitability_percent or 0) / 100), 2)
    await crud_module_types.recalc_section_cost(session, req.id, mt.id)
    return warnings


# ── Варианты расчёта ──


def _split(req: Request) -> tuple[str, int, str]:
    parsed = kso204.split_tkp_num(req.tkp_num or "")
    if not parsed:
        raise ValueError(f"Номер ТКП «{req.tkp_num}» не в формате «{req.id}-ив»: варианты недоступны")
    return parsed


async def list_variants(session: AsyncSession, req: Request) -> dict:
    """Варианты расчёта: сохранённые файлы КСО204 этой ТКП и текущий вариант."""
    base_id, current, _ = _split(req)
    files = kso204.list_variant_files(await get_tkp_folder(session, req), base_id)
    numbers = sorted(set(files) | {current})
    return {
        "current": current,
        "tkp_num": req.tkp_num,
        "variants": [
            {
                "n": n,
                "tkp_num": variant_tkp_num(req, n),
                "saved": n in files,
                "file": files[n].name if n in files else None,
            }
            for n in numbers
        ],
    }


def variant_tkp_num(req: Request, n: int) -> str:
    base_id, _, city = _split(req)
    return kso204.variant_tkp_num(base_id, n, city)


async def new_variant(session: AsyncSession, req: Request) -> tuple[Path, list[str]]:
    """Сохраняет текущий расчёт в файл и переводит ТКП на следующий номер варианта."""
    base_id, current, city = _split(req)
    path, warnings = await save_request_kso204(session, req)
    files = kso204.list_variant_files(path.parent, base_id)
    req.tkp_num = kso204.variant_tkp_num(base_id, max([current, *files]) + 1, city)
    await session.flush()
    return path, warnings


async def load_variant(session: AsyncSession, req: Request, n: int, save_current: bool) -> list[str]:
    """Переход к варианту n: расчёт КСО загружается из его файла, номер ТКП — номер варианта."""
    base_id, current, city = _split(req)
    folder = await get_tkp_folder(session, req)
    files = kso204.list_variant_files(folder, base_id)
    if n not in files:
        raise FileNotFoundError(f"Файл варианта {n} не найден")
    data = files[n].read_bytes()  # прочитать до возможной перезаписи текущего варианта
    warnings: list[str] = []
    if save_current and n != current:
        _, warnings = await save_request_kso204(session, req)
    warnings += await load_request_kso204(session, req, data)
    req.tkp_num = kso204.variant_tkp_num(base_id, n, city)
    await session.flush()
    return warnings
