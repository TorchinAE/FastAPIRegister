import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from openpyxl import Workbook, load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_module_types, crud_modules
from scr.dbase.database import db_helper
from scr.dbase.models import ModuleTypeDefault
from scr.dbase.schemas.schemas import (
    ModuleTypeCreateSchema,
    ModuleTypeDefaultCreateSchema,
    ModuleTypeDefaultResponseSchema,
    ModuleTypeResponseSchema,
    RequestCalcCreateSchema,
    RequestCalcItemCreateSchema,
    RequestCalcItemResponseSchema,
    RequestCalcItemUpdateSchema,
    RequestCalcResponseSchema,
    RequestCalcUpdateSchema,
)

mt_calc_router = APIRouter(tags=["ModuleTypes"])


# ── Module Types ──


@mt_calc_router.get("/api/module-types/", response_model=list[ModuleTypeResponseSchema])
async def list_module_types(session: AsyncSession = Depends(db_helper.session_dependency)):
    types = await crud_module_types.get_module_types(session)
    return [
        ModuleTypeResponseSchema(
            id=t.id,
            name=t.name,
            slug=t.slug,
            fot_item_id=t.fot_item_id,
            overhead_item_id=t.overhead_item_id,
            fot_item_name=t.fot_item.name if t.fot_item else None,
            fot_item_cost=float(t.fot_item.cost) if t.fot_item else 0,
            overhead_item_name=t.overhead_item.name if t.overhead_item else None,
            overhead_item_cost=float(t.overhead_item.cost) if t.overhead_item else 0,
            created_by=t.created_by,
        )
        for t in types
    ]


@mt_calc_router.post("/api/module-types/", response_model=ModuleTypeResponseSchema)
async def create_module_type(
    data: ModuleTypeCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    obj = await crud_module_types.add_module_type(session, data)
    await session.commit()
    return obj


@mt_calc_router.delete("/api/module-types/{type_id}")
async def delete_module_type(
    type_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_module_types.delete_module_type(session, type_id)
    if not result:
        raise HTTPException(status_code=404, detail="Тип модуля не найден")
    await session.commit()
    return {"ok": True}


@mt_calc_router.put("/api/module-types/{type_id}", response_model=ModuleTypeResponseSchema)
async def update_module_type(
    type_id: int,
    data: dict,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    mt = await crud_module_types.get_module_type_by_id(session, type_id)
    if not mt:
        raise HTTPException(status_code=404, detail="Тип модуля не найден")
    if "fot_item_id" in data:
        mt.fot_item_id = int(data["fot_item_id"]) if data["fot_item_id"] else None
    if "overhead_item_id" in data:
        mt.overhead_item_id = int(data["overhead_item_id"]) if data["overhead_item_id"] else None
    await session.flush()
    await session.commit()
    mt = await crud_module_types.get_module_type_by_id(session, type_id)
    return ModuleTypeResponseSchema(
        id=mt.id,
        name=mt.name,
        slug=mt.slug,
        fot_item_id=mt.fot_item_id,
        overhead_item_id=mt.overhead_item_id,
        fot_item_name=mt.fot_item.name if mt.fot_item else None,
        fot_item_cost=float(mt.fot_item.cost) if mt.fot_item else 0,
        overhead_item_name=mt.overhead_item.name if mt.overhead_item else None,
        overhead_item_cost=float(mt.overhead_item.cost) if mt.overhead_item else 0,
        created_by=mt.created_by,
    )


# ── Module Type Defaults ──


@mt_calc_router.get("/api/module-types/{type_id}/defaults", response_model=list[ModuleTypeDefaultResponseSchema])
async def list_defaults(
    type_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    defaults = await crud_module_types.get_defaults(session, type_id)
    prices = await crud_modules.get_module_prices(session)
    return [
        ModuleTypeDefaultResponseSchema(
            id=d.id,
            module_type_id=d.module_type_id,
            module_id=d.module_id,
            quantity=d.quantity,
            module_name=d.module.name if d.module else None,
            module_price=prices.get(d.module_id, 0.0),
        )
        for d in defaults
    ]


@mt_calc_router.post("/api/module-types/{type_id}/defaults", response_model=ModuleTypeDefaultResponseSchema)
async def create_default(
    type_id: int,
    data: ModuleTypeDefaultCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.module_type_id = type_id
    obj = await crud_module_types.add_default(session, data)
    await session.commit()
    return ModuleTypeDefaultResponseSchema(
        id=obj.id,
        module_type_id=obj.module_type_id,
        module_id=obj.module_id,
        quantity=obj.quantity,
    )


_DEFAULTS_ALIASES = {
    "id": "id",
    "id модуля": "id",
    "модуль": "name",
    "название": "name",
    "наименование": "name",
    "кол-во": "qty",
    "количество": "qty",
}


@mt_calc_router.get("/api/module-types/{type_id}/defaults/export-excel")
async def export_defaults_excel(
    type_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    from datetime import datetime as dt

    from openpyxl.styles import Font

    from scr.utils.excel import MONEY_FMT, auto_fit_columns, border_row, safe_filename, write_header, xlsx_response

    mt = await crud_module_types.get_module_type_by_id(session, type_id)
    if not mt:
        raise HTTPException(status_code=404, detail="Тип модуля не найден")
    defaults = await crud_module_types.get_defaults(session, type_id)
    prices = await crud_modules.get_module_prices(session)

    wb = Workbook()
    ws = wb.active
    ws.title = "Модули по умолчанию"
    headers = ["ID", "Модуль", "Кол-во", "Цена за ед.", "Сумма"]
    ws.append([f"{mt.name} — модули по умолчанию"])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.cell(1, 1).font = Font(bold=True, size=14)
    write_header(ws, headers)
    for d in defaults:
        ws.append([d.module_id, d.module.name if d.module else "", d.quantity, prices.get(d.module_id, 0.0)])
        row_num = ws.max_row
        ws.cell(row_num, 5).value = f"=C{row_num}*D{row_num}"
        ws.cell(row_num, 4).number_format = MONEY_FMT
        ws.cell(row_num, 5).number_format = MONEY_FMT
        border_row(ws, row_num, len(headers))
    auto_fit_columns(ws)
    return xlsx_response(wb, f"defaults_{safe_filename(mt.slug)}_{dt.now().strftime('%Y%m%d')}.xlsx")


@mt_calc_router.post("/api/module-types/{type_id}/defaults/import-excel")
async def import_defaults_excel(
    type_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    """Модуль ищется по ID, затем по названию. Уже добавленный модуль — количество заменяется."""
    from scr.utils.excel import cell, data_rows, find_header, to_int

    mt = await crud_module_types.get_module_type_by_id(session, type_id)
    if not mt:
        raise HTTPException(status_code=404, detail="Тип модуля не найден")
    try:
        wb = load_workbook(io.BytesIO(await file.read()), data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Не удалось прочитать файл Excel") from exc
    rows = list(wb.active.iter_rows(values_only=True))
    header_idx, col_map = find_header(rows, _DEFAULTS_ALIASES, required="name")
    if header_idx < 0:
        raise HTTPException(status_code=400, detail="Не найдена строка заголовка с колонкой «Модуль»")

    existing = {d.module_id: d for d in await crud_module_types.get_defaults(session, type_id)}
    added = updated = 0
    skipped: list[str] = []
    for row in data_rows(rows, header_idx):
        name = cell(row, col_map, "name")
        name = str(name).strip() if name is not None else None
        row_id = to_int(cell(row, col_map, "id"))
        if not name and not row_id:
            continue
        mod = await crud_modules.get_module_by_id(session, row_id) if row_id else None
        if not mod and name:
            mod = await crud_modules.get_module_by_name(session, name)
        if not mod:
            skipped.append(name or f"ID {row_id}")
            continue
        qty = to_int(cell(row, col_map, "qty"), 1)
        if qty is None or qty < 1:
            skipped.append(f"{mod.name}: количество {qty}")
            continue
        if mod.id in existing:
            existing[mod.id].quantity = qty
            updated += 1
        else:
            obj = ModuleTypeDefault(module_type_id=type_id, module_id=mod.id, quantity=qty)
            session.add(obj)
            existing[mod.id] = obj
            added += 1
    await session.commit()
    message = f"Добавлено: {added}, обновлено: {updated}"
    if skipped:
        message += f", не найдено: {', '.join(skipped)}"
    return {"message": message, "added": added, "updated": updated, "skipped": skipped}


@mt_calc_router.patch("/api/module-types/defaults/{default_id}")
async def update_default(
    default_id: int,
    data: dict,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    obj = await session.get(ModuleTypeDefault, default_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    if "quantity" in data:
        obj.quantity = int(data["quantity"])
    await session.flush()
    await session.commit()
    return {"ok": True}


@mt_calc_router.delete("/api/module-types/defaults/{default_id}")
async def delete_default(
    default_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_module_types.delete_default(session, default_id)
    if not result:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    await session.commit()
    return {"ok": True}


# ── RequestCalcs ──


@mt_calc_router.post("/api/request-calcs/")
async def create_calc(
    data: RequestCalcCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    """Новый блок расчёта со значениями по умолчанию. Возвращает данные блока для страницы."""
    if not await crud_module_types.get_module_type_by_id(session, data.module_type_id):
        raise HTTPException(status_code=404, detail="Тип модуля не найден")
    calc = await crud_module_types.create_calc(session, data.request_id, data.module_type_id)
    section_cost = await crud_module_types.recalc_section_cost(session, data.request_id, data.module_type_id)
    await session.commit()
    prices = await crud_modules.get_module_prices(session)
    default_profit = await crud_module_types.default_profitability(session, data.request_id)
    return {
        "block": crud_module_types.calc_block_data(calc, prices, default_profit),
        "section_cost": section_cost,
    }


@mt_calc_router.delete("/api/request-calcs/{calc_id}")
async def delete_calc(
    calc_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    calc = await crud_module_types.delete_calc(session, calc_id)
    if not calc:
        raise HTTPException(status_code=404, detail="Расчёт не найден")
    section_cost = await crud_module_types.recalc_section_cost(session, calc.request_id, calc.module_type_id)
    await session.commit()
    return {"ok": True, "section_cost": section_cost}


@mt_calc_router.get("/api/request-calcs/{calc_id}", response_model=RequestCalcResponseSchema)
async def get_calc(
    calc_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    calc = await crud_module_types.get_calc_by_id(session, calc_id)
    if not calc:
        raise HTTPException(status_code=404, detail="Расчёт не найден")
    return calc


@mt_calc_router.put("/api/request-calcs/{calc_id}", response_model=RequestCalcResponseSchema)
async def update_calc(
    calc_id: int,
    data: RequestCalcUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = calc_id
    result = await crud_module_types.update_calc(session, data)
    if not result:
        raise HTTPException(status_code=404, detail="Расчёт не найден")
    await crud_module_types.recalc_section_cost(session, result.request_id, result.module_type_id)
    await session.commit()
    return result


@mt_calc_router.post("/api/request-calcs/{calc_id}/items", response_model=RequestCalcItemResponseSchema)
async def add_calc_item(
    calc_id: int,
    data: RequestCalcItemCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.calc_id = calc_id
    obj = await crud_module_types.add_calc_item(session, data)
    await session.commit()
    await session.refresh(obj, attribute_names=["module"])
    prices = await crud_modules.get_module_prices(session)
    return RequestCalcItemResponseSchema(
        id=obj.id,
        calc_id=obj.calc_id,
        module_id=obj.module_id,
        quantity=obj.quantity,
        module_name=obj.module.name if obj.module else None,
        module_price=prices.get(obj.module_id, 0.0),
    )


@mt_calc_router.patch("/api/request-calcs/items/{item_id}", response_model=RequestCalcItemResponseSchema)
async def update_calc_item(
    item_id: int,
    data: RequestCalcItemUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = item_id
    result = await crud_module_types.update_calc_item(session, data)
    if not result:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    await session.commit()
    await session.refresh(result, attribute_names=["module"])
    prices = await crud_modules.get_module_prices(session)
    return RequestCalcItemResponseSchema(
        id=result.id,
        calc_id=result.calc_id,
        module_id=result.module_id,
        quantity=result.quantity,
        module_name=result.module.name if result.module else None,
        module_price=prices.get(result.module_id, 0.0),
    )


@mt_calc_router.delete("/api/request-calcs/items/{item_id}")
async def delete_calc_item(
    item_id: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_module_types.delete_calc_item(session, item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    await session.commit()
    return {"ok": True}
