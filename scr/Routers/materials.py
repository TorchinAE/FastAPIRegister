import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_materials
from scr.dbase.database import db_helper
from scr.dbase.schemas.schemas import (
    MaterialCreateSchema,
    MaterialResponseSchema,
    MaterialUpdateSchema,
    PaginatedResponse,
)

mat_router = APIRouter(prefix="/api/materials", tags=["Materials"])


@mat_router.post("/", response_model=MaterialResponseSchema)
async def add_material(
    data: MaterialCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new_mat = await crud_materials.add_material(session=session, in_mat=data)
    await session.commit()
    return new_mat


@mat_router.get("/", response_model=PaginatedResponse)
async def read_materials(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items, total = await crud_materials.get_materials(session=session, search=search, page=page, per_page=per_page)
    return PaginatedResponse(
        items=[MaterialResponseSchema.model_validate(i) for i in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@mat_router.get("/all", response_model=list[MaterialResponseSchema])
async def read_all_materials(
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items = await crud_materials.get_all_materials(session=session)
    return items


@mat_router.get("/export-excel")
async def export_materials_excel(
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items = await crud_materials.get_all_materials(session=session)
    wb = Workbook()
    ws = wb.active
    ws.title = "Материалы"
    ws.append(["ID", "Название", "Цена", "Код 1С", "Код агент", "URL агент"])
    for item in items:
        ws.append(
            [item.id, item.name, float(item.price), item.code_1c or "", item.code_agent or "", item.url_agent or ""]
        )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=materials.xlsx"},
    )


@mat_router.post("/import-excel")
async def import_materials_excel(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    content = await file.read()
    wb = load_workbook(io.BytesIO(content))
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    imported = 0
    for row in rows:
        if not row or not row[0]:
            continue
        name = str(row[0]).strip()
        if not name:
            continue
        price = float(row[1]) if len(row) > 1 and row[1] else 0
        code_1c = str(row[2]).strip() if len(row) > 2 and row[2] else None
        code_agent = str(row[3]).strip() if len(row) > 3 and row[3] else None
        url_agent = str(row[4]).strip() if len(row) > 4 and row[4] else None
        await crud_materials.add_material(
            session,
            MaterialCreateSchema(name=name, price=price, code_1c=code_1c, code_agent=code_agent, url_agent=url_agent),
        )
        imported += 1
    await session.commit()
    return {"message": f"Импортировано: {imported}", "imported": imported}


@mat_router.get("/{mat_id}", response_model=MaterialResponseSchema)
async def read_material(mat_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    mat = await crud_materials.get_material_by_id(session=session, mat_id=mat_id)
    if not mat:
        raise HTTPException(status_code=404, detail="Материал не найден")
    return mat


@mat_router.patch("/", response_model=MaterialResponseSchema)
async def update_material(
    data: MaterialUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_materials.update_material(session=session, upd_mat=data)
    if not result:
        raise HTTPException(status_code=404, detail="Материал не найден")
    await session.commit()
    return result


@mat_router.delete("/{mat_id}")
async def delete_material(mat_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    result = await crud_materials.delete_material(session=session, mat_id=mat_id)
    if not result:
        raise HTTPException(status_code=404, detail="Материал не найден")
    await session.commit()
    return {"message": "Материал удалён"}
