import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_modules
from scr.dbase.database import db_helper
from scr.dbase.schemas.schemas import (
    MaterialResponseSchema,
    ModuleCreateSchema,
    ModuleFullResponseSchema,
    ModuleItemCreateSchema,
    ModuleItemResponseSchema,
    ModuleResponseSchema,
    ModuleUpdateSchema,
    PaginatedResponse,
)

mod_router = APIRouter(prefix="/api/modules", tags=["Modules"])


def _module_to_response(mod) -> ModuleResponseSchema:
    return ModuleResponseSchema(
        id=mod.id,
        name=mod.name,
        items_count=mod.items_count,
        total_price=mod.total_price,
        created_by=mod.created_by,
    )


def _module_item_to_response(item) -> ModuleItemResponseSchema:
    return ModuleItemResponseSchema(
        id=item.id,
        module_id=item.module_id,
        material_id=item.material_id,
        sub_module_id=item.sub_module_id,
        quantity=item.quantity,
        material=MaterialResponseSchema.model_validate(item.material) if item.material else None,
        sub_module_name=item.sub_module.name if item.sub_module else None,
    )


@mod_router.post("/", response_model=ModuleResponseSchema)
async def add_module(
    data: ModuleCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new_mod = await crud_modules.add_module(session=session, in_mod=data)
    await session.commit()
    await session.refresh(new_mod)
    return _module_to_response(new_mod)


@mod_router.get("/", response_model=PaginatedResponse)
async def read_modules(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items, total = await crud_modules.get_modules(session=session, search=search, page=page, per_page=per_page)
    return PaginatedResponse(
        items=[_module_to_response(i) for i in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@mod_router.get("/all", response_model=list[ModuleResponseSchema])
async def read_all_modules(
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items = await crud_modules.get_all_modules(session=session)
    return [_module_to_response(i) for i in items]


@mod_router.get("/export-excel")
async def export_modules_excel(
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    from openpyxl.styles import Border, Font, PatternFill, Side

    modules = await crud_modules.get_all_modules(session=session)
    wb = Workbook()

    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    def _style_header(ws, cols, row_num=1):
        for col_idx in range(1, cols + 1):
            cell = ws.cell(row_num, col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border

    def _style_row(ws, row_num, cols):
        for col_idx in range(1, cols + 1):
            ws.cell(row_num, col_idx).border = thin_border

    ws1 = wb.active
    ws1.title = "Модули"
    ws1.append(["ID", "Название", "Компонентов", "Стоимость"])
    _style_header(ws1, 4)
    for mod in modules:
        ws1.append([mod.id, mod.name, mod.items_count, float(mod.total_price)])
        _style_row(ws1, ws1.max_row, 4)
        ws1.cell(ws1.max_row, 4).number_format = "# ##0.00"

    ws2 = wb.create_sheet("Состав")
    ws2.append(["Модуль", "Тип компонента", "Название компонента", "Количество"])
    _style_header(ws2, 4)
    for mod in modules:
        items = await crud_modules.get_module_items(session, mod.id)
        for item in items:
            if item.material:
                ws2.append([mod.name, "материал", item.material.name, item.quantity])
            elif item.sub_module:
                ws2.append([mod.name, "модуль", item.sub_module.name, item.quantity])
            _style_row(ws2, ws2.max_row, 4)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=modules.xlsx"},
    )


@mod_router.post("/import-excel")
async def import_modules_excel(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    content = await file.read()
    wb = load_workbook(io.BytesIO(content))

    imported = 0
    if "Модули" in wb.sheetnames:
        ws = wb["Модули"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            name = str(row[0]).strip() if row[0] else None
            if not name:
                continue
            await crud_modules.add_module(session, ModuleCreateSchema(name=name))
            imported += 1

    if "Состав" in wb.sheetnames:
        ws = wb["Состав"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            mod_name = str(row[0]).strip()
            mod = await crud_modules.get_module_by_name(session, mod_name)
            if not mod:
                continue
            item_type = str(row[1]).strip() if row[1] else ""
            item_name = str(row[2]).strip() if row[2] else ""
            quantity = int(row[3]) if row[3] else 1
            if item_type == "материал":
                from scr.dbase import crud_materials

                mat = await crud_materials.get_material_by_name(session, item_name)
                if mat:
                    await crud_modules.add_module_item(
                        session,
                        mod.id,
                        ModuleItemCreateSchema(material_id=mat.id, quantity=quantity),
                    )
            elif item_type == "модуль":
                sub_mod = await crud_modules.get_module_by_name(session, item_name)
                if sub_mod:
                    await crud_modules.add_module_item(
                        session,
                        mod.id,
                        ModuleItemCreateSchema(sub_module_id=sub_mod.id, quantity=quantity),
                    )

    await session.commit()
    return {"message": f"Импортировано модулей: {imported}", "imported": imported}


@mod_router.get("/{mod_id}/export-excel")
async def export_module_excel(mod_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    from openpyxl.styles import Border, Font, PatternFill, Side

    mod = await crud_modules.get_module_by_id(session=session, mod_id=mod_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Модуль не найден")

    wb = Workbook()
    ws = wb.active
    ws.title = "Состав модуля"

    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    money_fmt = "# ##0.00"
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    async def _bom_flat(module, qty=1):
        result = []
        for it in module.items:
            if it.material:
                result.append(
                    {"name": it.material.name, "price": float(it.material.price), "quantity": it.quantity * qty}
                )
            elif it.sub_module:
                sub = await crud_modules.get_module_by_id(session, it.sub_module.id)
                if sub:
                    result.extend(await _bom_flat(sub, it.quantity * qty))
        return result

    # Row 1: module name
    ws.append([mod.name])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=5)
    ws.cell(1, 1).font = Font(bold=True, size=14)

    # Row 2: headers
    headers = ["Тип", "Название", "Цена за ед.", "Количество", "Сумма"]
    ws.append(headers)
    for col_idx, _ in enumerate(headers, 1):
        cell = ws.cell(2, col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border

    # Rows 3+: items
    for item in mod.items:
        if item.material:
            row_data = ["Материал", item.material.name, float(item.material.price), item.quantity, None]
        elif item.sub_module:
            row_data = ["Модуль", item.sub_module.name, float(item.sub_module.total_price), item.quantity, None]
        else:
            continue
        ws.append(row_data)
        row_num = ws.max_row
        ws.cell(row_num, 3).number_format = money_fmt
        ws.cell(row_num, 5).number_format = money_fmt
        # SUM formula: price * quantity
        ws.cell(row_num, 5).value = f"=C{row_num}*D{row_num}"
        for col_idx in range(1, 6):
            ws.cell(row_num, col_idx).border = thin_border

    # Total row with SUM formula
    items_start = 3
    items_end = ws.max_row
    ws.append(["", "", "", "Итого:", f"=SUM(E{items_start}:E{items_end})"])
    total_row = ws.max_row
    ws.cell(total_row, 4).font = Font(bold=True)
    ws.cell(total_row, 5).font = Font(bold=True)
    ws.cell(total_row, 5).number_format = money_fmt
    for col_idx in range(1, 6):
        ws.cell(total_row, col_idx).border = thin_border

    # BOM section
    bom_items = await _bom_flat(mod)
    if bom_items:
        ws.append([])
        ws.append(["Раскрытие состава (BOM)"])
        bom_title_row = ws.max_row
        ws.merge_cells(start_row=bom_title_row, start_column=1, end_row=bom_title_row, end_column=5)
        ws.cell(bom_title_row, 1).font = Font(bold=True, size=12)

        bom_headers = ["", "Материал", "Цена за ед.", "Кол-во", "Сумма"]
        ws.append(bom_headers)
        bom_hdr_row = ws.max_row
        for col_idx, _ in enumerate(bom_headers, 1):
            cell = ws.cell(bom_hdr_row, col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border

        for bi in bom_items:
            ws.append(["", bi["name"], bi["price"], bi["quantity"], None])
            row_num = ws.max_row
            ws.cell(row_num, 3).number_format = money_fmt
            ws.cell(row_num, 5).number_format = money_fmt
            ws.cell(row_num, 5).value = f"=C{row_num}*D{row_num}"
            for col_idx in range(1, 6):
                ws.cell(row_num, col_idx).border = thin_border

        bom_start = bom_hdr_row + 1
        bom_end = ws.max_row
        ws.append(["", "", "", "Итого:", f"=SUM(E{bom_start}:E{bom_end})"])
        bom_total_row = ws.max_row
        ws.cell(bom_total_row, 4).font = Font(bold=True)
        ws.cell(bom_total_row, 5).font = Font(bold=True)
        ws.cell(bom_total_row, 5).number_format = money_fmt
        for col_idx in range(1, 6):
            ws.cell(bom_total_row, col_idx).border = thin_border

    # Column widths
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 16

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=module_{mod_id}.xlsx"},
    )


@mod_router.post("/{mod_id}/duplicate", response_model=ModuleFullResponseSchema)
async def duplicate_module(mod_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    mod = await crud_modules.get_module_by_id(session=session, mod_id=mod_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    new_name = f"{mod.name} - копия"
    new_mod = await crud_modules.add_module(session=session, in_mod=ModuleCreateSchema(name=new_name))
    await session.flush()
    for item in mod.items:
        await crud_modules.add_module_item(
            session,
            new_mod.id,
            ModuleItemCreateSchema(
                material_id=item.material_id,
                sub_module_id=item.sub_module_id,
                quantity=item.quantity,
            ),
        )
    await session.commit()
    new_mod = await crud_modules.get_module_by_id(session=session, mod_id=new_mod.id)
    items_resp = [_module_item_to_response(i) for i in new_mod.items]
    return ModuleFullResponseSchema(
        id=new_mod.id,
        name=new_mod.name,
        items=items_resp,
        total_price=new_mod.total_price,
        created_by=new_mod.created_by,
    )


@mod_router.get("/{mod_id}", response_model=ModuleFullResponseSchema)
async def read_module(mod_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    mod = await crud_modules.get_module_by_id(session=session, mod_id=mod_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    items_resp = [_module_item_to_response(i) for i in mod.items]
    return ModuleFullResponseSchema(
        id=mod.id,
        name=mod.name,
        items=items_resp,
        total_price=mod.total_price,
        created_by=mod.created_by,
    )


@mod_router.patch("/", response_model=ModuleResponseSchema)
async def update_module(
    data: ModuleUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_modules.update_module(session=session, upd_mod=data)
    if not result:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    await session.commit()
    await session.refresh(result)
    return _module_to_response(result)


@mod_router.delete("/{mod_id}")
async def delete_module(mod_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    result = await crud_modules.delete_module(session=session, mod_id=mod_id)
    if not result:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    await session.commit()
    return {"message": "Модуль удалён"}


@mod_router.post("/{mod_id}/items", response_model=ModuleItemResponseSchema)
async def add_module_item(
    mod_id: int,
    data: ModuleItemCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    item = await crud_modules.add_module_item(session, mod_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    await session.commit()
    await session.refresh(item)
    # Eagerly load relationships after commit (they get expired)
    if item.material_id:
        await session.refresh(item, ["material"])
    if item.sub_module_id:
        await session.refresh(item, ["sub_module"])
    return _module_item_to_response(item)


@mod_router.patch("/items/{item_id}", response_model=ModuleItemResponseSchema)
async def update_module_item(
    item_id: int,
    data: dict,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    quantity = data.get("quantity", 1)
    item = await crud_modules.update_module_item_quantity(session, item_id, quantity)
    if not item:
        raise HTTPException(status_code=404, detail="Элемент не найден")
    await session.commit()
    await session.refresh(item)
    if item.material_id:
        await session.refresh(item, ["material"])
    if item.sub_module_id:
        await session.refresh(item, ["sub_module"])
    return _module_item_to_response(item)


@mod_router.delete("/items/{item_id}")
async def delete_module_item(item_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    result = await crud_modules.delete_module_item(session, item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Элемент не найден")
    await session.commit()
    return {"message": "Элемент удалён"}
