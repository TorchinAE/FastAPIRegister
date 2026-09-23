import io
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from openpyxl import Workbook, load_workbook

from scr.dbase.database import db_helper
from scr.dbase import crud_modules
from scr.dbase.schemas.schemas import (
    ModuleCreateSchema,
    ModuleUpdateSchema,
    ModuleResponseSchema,
    ModuleFullResponseSchema,
    ModuleItemCreateSchema,
    ModuleItemResponseSchema,
    MaterialResponseSchema,
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
    items, total = await crud_modules.get_modules(
        session=session, search=search, page=page, per_page=per_page
    )
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
    modules = await crud_modules.get_all_modules(session=session)
    wb = Workbook()

    ws1 = wb.active
    ws1.title = "Модули"
    ws1.append(["ID", "Название"])
    for mod in modules:
        ws1.append([mod.id, mod.name])

    ws2 = wb.create_sheet("Состав")
    ws2.append(["Модуль", "Тип компонента", "Название компонента", "Количество"])
    for mod in modules:
        items = await crud_modules.get_module_items(session, mod.id)
        for item in items:
            if item.material:
                ws2.append([mod.name, "материал", item.material.name, item.quantity])
            elif item.sub_module:
                ws2.append([mod.name, "модуль", item.sub_module.name, item.quantity])

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
                        session, mod.id,
                        ModuleItemCreateSchema(material_id=mat.id, quantity=quantity),
                    )
            elif item_type == "модуль":
                sub_mod = await crud_modules.get_module_by_name(session, item_name)
                if sub_mod:
                    await crud_modules.add_module_item(
                        session, mod.id,
                        ModuleItemCreateSchema(sub_module_id=sub_mod.id, quantity=quantity),
                    )

    await session.commit()
    return {"message": f"Импортировано модулей: {imported}", "imported": imported}


@mod_router.get("/{mod_id}", response_model=ModuleFullResponseSchema)
async def read_module(
    mod_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
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
async def delete_module(
    mod_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
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
    return _module_item_to_response(item)


@mod_router.delete("/items/{item_id}")
async def delete_module_item(
    item_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    result = await crud_modules.delete_module_item(session, item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Элемент не найден")
    await session.commit()
    return {"message": "Элемент удалён"}
