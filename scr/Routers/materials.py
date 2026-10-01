import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_material_types, crud_materials
from scr.dbase.database import db_helper
from scr.dbase.schemas.schemas import (
    MaterialCreateSchema,
    MaterialResponseSchema,
    MaterialTypeCreateSchema,
    MaterialUpdateSchema,
    PaginatedResponse,
)

mat_router = APIRouter(prefix="/api/materials", tags=["Materials"])


def _mat_response(mat) -> MaterialResponseSchema:
    return MaterialResponseSchema(
        id=mat.id,
        name=mat.name,
        price=float(mat.price),
        code_1c=mat.code_1c,
        code_agent=mat.code_agent,
        url_agent=mat.url_agent,
        type_id=mat.type_id,
        type_name=mat.type.name if mat.type else None,
        created_by=mat.created_by,
        date=mat.date,
    )


@mat_router.post("/", response_model=MaterialResponseSchema)
async def add_material(
    data: MaterialCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new_mat = await crud_materials.add_material(session=session, in_mat=data)
    await session.commit()
    await session.refresh(new_mat, ["type"])
    return _mat_response(new_mat)


@mat_router.get("/", response_model=PaginatedResponse)
async def read_materials(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items, total = await crud_materials.get_materials(session=session, search=search, page=page, per_page=per_page)
    return PaginatedResponse(
        items=[_mat_response(i) for i in items],
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
    return [_mat_response(i) for i in items]


@mat_router.get("/export-excel")
async def export_materials_excel(
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    from datetime import datetime as dt

    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    items = await crud_materials.get_all_materials(session=session)
    wb = Workbook()
    ws = wb.active
    ws.title = "Материалы"

    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # Title row
    headers = [
        "ID",
        "Тип",
        "Название",
        "Цена",
        "Дата",
        "Ном Ток",
        "стац",
        "втыч",
        "выкат",
        "ручн",
        "эл.прив",
        "Код 1С",
        "Код агент",
        "URL агент",
    ]
    num_cols = len(headers)
    ws.append(["Материалы"])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_cols)
    ws.cell(1, 1).font = Font(bold=True, size=14)
    ws.cell(1, 1).alignment = Alignment(horizontal="center")

    ws.append(headers)
    for col_idx in range(1, num_cols + 1):
        cell = ws.cell(2, col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border

    for item in items:
        ws.append(
            [
                item.id,
                item.type.name if item.type else "",
                item.name,
                float(item.price),
                item.date.strftime("%d.%m.%Y") if item.date else "",
                item.nom_tok,
                "+" if item.stats else "",
                "+" if item.vtych else "",
                "+" if item.vykat else "",
                "+" if item.ruchn else "",
                "+" if item.el_priv else "",
                item.code_1c or "",
                item.code_agent or "",
                item.url_agent or "",
            ]
        )
        row_num = ws.max_row
        ws.cell(row_num, 4).number_format = "# ##0.00"
        for col_idx in range(1, num_cols + 1):
            ws.cell(row_num, col_idx).border = thin_border

    # Auto-fit columns
    from openpyxl.utils import get_column_letter

    for col_cells in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col_cells[0].column)
        for cell in col_cells:
            if cell.value is not None:
                cell_len = len(str(cell.value))
                max_len = max(max_len, cell_len)
        ws.column_dimensions[col_letter].width = min(max_len + 3, 60)

    date_str = dt.now().strftime("%Y%m%d")
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"materials_{date_str}.xlsx"
    from urllib.parse import quote

    encoded = quote(filename)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


@mat_router.post("/import-excel")
async def import_materials_excel(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    content = await file.read()
    wb = load_workbook(io.BytesIO(content))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    # Phase 1: scan for price changes (same-price rows are conflicts)
    conflicts = []
    new_rows = []
    for parsed in _parse_rows(rows):
        existing = await _find_existing(session, parsed)
        if existing and float(existing.price) == parsed["price"] and parsed["price"] > 0:
            conflicts.append(
                {
                    "id": existing.id,
                    "name": parsed["name"],
                    "old_name": existing.name,
                    "price": parsed["price"],
                    "old_price": float(existing.price),
                }
            )
        new_rows.append(parsed)

    if conflicts:
        return {"status": "confirm", "conflicts": conflicts, "total": len(new_rows)}

    imported = await _do_import(session, rows)
    await session.commit()
    return {"status": "ok", "message": f"Импортировано: {imported}", "imported": imported}


@mat_router.post("/import-excel-confirm")
async def import_materials_excel_confirm(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    """Import with overwrite confirmation — user already confirmed."""
    content = await file.read()
    wb = load_workbook(io.BytesIO(content))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    imported = await _do_import(session, rows)
    await session.commit()
    return {"status": "ok", "message": f"Импортировано: {imported}", "imported": imported}


def _parse_rows(rows: list) -> list[dict]:
    """Parse rows into normalized dicts. Detects columns by header or falls back to fixed order."""
    parsed_list = []
    if not rows:
        return parsed_list

    # Try to detect header row
    col_map = _detect_header(rows[0])
    data_start = 0
    if col_map is not None:
        data_start = 1  # skip header row

    for row in rows[data_start:]:
        if not row:
            continue

        if col_map is not None:
            parsed = _parse_by_header(row, col_map)
        else:
            parsed = _parse_fixed(row)

        if parsed and parsed.get("name"):
            parsed_list.append(parsed)

    return parsed_list


# Known column name aliases → canonical field names
_HEADER_ALIASES = {
    "id": "id",
    "код": "id",
    "название": "name",
    "наименование": "name",
    "имя": "name",
    "материал": "name",
    "цена": "price",
    "стоимость": "price",
    "тип": "type",
    "тип материала": "type",
    "дата": "date",
    "дата цены": "date",
    "ном ток": "nom_tok",
    "ном. ток": "nom_tok",
    "ном_tok": "nom_tok",
    "стац": "stats",
    "втыч": "vtych",
    "выкат": "vykat",
    "ручн": "ruchn",
    "ручная": "ruchn",
    "эл.прив": "el_priv",
    "эл прив": "el_priv",
    "электропривод": "el_priv",
    "код 1с": "code_1c",
    "код 1c": "code_1c",
    "code_1c": "code_1c",
    "1c": "code_1c",
    "код агент": "code_agent",
    "code_agent": "code_agent",
    "агент": "code_agent",
    "url агент": "url_agent",
    "url_agent": "url_agent",
    "url": "url_agent",
    "ссылка": "url_agent",
}


def _detect_header(row) -> dict | None:
    """If row looks like a header, return {canonical_name: col_index} mapping."""
    if not row:
        return None
    mapping = {}
    for i, cell in enumerate(row):
        if cell is None:
            continue
        key = str(cell).strip().lower()
        canonical = _HEADER_ALIASES.get(key)
        if canonical:
            mapping[canonical] = i
    # Need at least "name" to be useful
    if "name" in mapping:
        return mapping
    return None


def _get(row, col_map, field, default=None):
    """Get value from row by field name via col_map."""
    idx = col_map.get(field)
    if idx is None or idx >= len(row):
        return default
    val = row[idx]
    if val is None:
        return default
    return val


def _parse_by_header(row, col_map: dict) -> dict | None:
    """Parse a single row using header-based column mapping."""
    name = str(_get(row, col_map, "name", "")).strip()
    if not name:
        return None

    price = 0
    raw_price = _get(row, col_map, "price")
    if raw_price is not None:
        try:
            price = float(raw_price)
        except (ValueError, TypeError):
            price = 0

    row_id = None
    raw_id = _get(row, col_map, "id")
    if raw_id is not None:
        try:
            row_id = int(raw_id)
        except (ValueError, TypeError):
            row_id = None

    nom_tok = 0
    raw_nom = _get(row, col_map, "nom_tok")
    if raw_nom is not None:
        try:
            nom_tok = int(raw_nom)
        except (ValueError, TypeError):
            nom_tok = 0

    return {
        "row_id": row_id,
        "type_name": str(_get(row, col_map, "type", "")).strip() or None,
        "name": name,
        "price": price,
        "date": _parse_date(_get(row, col_map, "date")),
        "nom_tok": nom_tok,
        "stats": bool(_get(row, col_map, "stats", True)),
        "vtych": bool(_get(row, col_map, "vtych", False)),
        "vykat": bool(_get(row, col_map, "vykat", False)),
        "ruchn": bool(_get(row, col_map, "ruchn", True)),
        "el_priv": bool(_get(row, col_map, "el_priv", False)),
        "code_1c": str(_get(row, col_map, "code_1c", "")).strip() or None,
        "code_agent": str(_get(row, col_map, "code_agent", "")).strip() or None,
        "url_agent": str(_get(row, col_map, "url_agent", "")).strip() or None,
    }


def _parse_fixed(row) -> dict | None:
    """Fallback: parse row assuming old format (name, price, code_1c, code_agent, url_agent, type, id)."""
    if not row or not row[0]:
        return None
    # Skip obvious header text
    first = str(row[0]).strip().lower()
    if first in ("id", "название", "материалы", "наименование"):
        return None

    name = str(row[0]).strip()
    if not name:
        return None

    # Detect which column holds the price
    price = 0
    price_col = 1
    if len(row) > 1 and row[1] is not None:
        try:
            price = float(row[1])
        except (ValueError, TypeError):
            # row[1] is not a number — try row[2] as price
            price_col = 2
            if len(row) > 2 and row[2] is not None:
                try:
                    price = float(row[2])
                except (ValueError, TypeError):
                    price = 0

    # code_1c is the column after the price
    code_1c_col = price_col + 1
    code_1c = str(row[code_1c_col]).strip() if len(row) > code_1c_col and row[code_1c_col] else None
    code_agent_col = code_1c_col + 1
    code_agent = str(row[code_agent_col]).strip() if len(row) > code_agent_col and row[code_agent_col] else None
    url_agent_col = code_agent_col + 1
    url_agent = str(row[url_agent_col]).strip() if len(row) > url_agent_col and row[url_agent_col] else None

    return {
        "row_id": None,
        "type_name": None,
        "name": name,
        "price": price,
        "date": None,
        "nom_tok": 0,
        "stats": True,
        "vtych": False,
        "vykat": False,
        "ruchn": True,
        "el_priv": False,
        "code_1c": code_1c,
        "code_agent": code_agent,
        "url_agent": url_agent,
    }


def _parse_date(val):
    from datetime import date
    from datetime import datetime as dt

    if not val:
        return None
    if isinstance(val, dt):
        return val.date()
    try:
        return dt.strptime(str(val).strip(), "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        pass
    try:
        return dt.strptime(str(val).strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


async def _find_existing(session: AsyncSession, parsed: dict):
    """Find existing material by: ID → code_1c → code_agent → name."""
    if parsed.get("row_id"):
        mat = await crud_materials.get_material_by_id(session, parsed["row_id"])
        if mat:
            return mat
    if parsed.get("code_1c"):
        mat = await crud_materials.get_material_by_code_1c(session, parsed["code_1c"])
        if mat:
            return mat
    if parsed.get("code_agent"):
        mat = await crud_materials.get_material_by_code_agent(session, parsed["code_agent"])
        if mat:
            return mat
    return await crud_materials.get_material_by_name(session, parsed["name"])


async def _do_import(session: AsyncSession, rows: list) -> int:
    from datetime import date as date_cls

    # Cache all material types for auto-creation
    types_cache, _ = await crud_material_types.get_all_types(session, per_page=10000)
    types_map = {t.name: t.id for t in types_cache}

    # Ensure default type "Производство" exists
    if "Производство" not in types_map:
        new_type = await crud_material_types.add_type(session, MaterialTypeCreateSchema(name="Производство"))
        types_map["Производство"] = new_type.id

    imported = 0
    for parsed in _parse_rows(rows):
        existing = await _find_existing(session, parsed)

        # Resolve type_id
        type_name = parsed.get("type_name")
        if not type_name:
            type_name = "Производство"
        type_id = None
        if type_name:
            if type_name not in types_map:
                new_type = await crud_material_types.add_type(session, MaterialTypeCreateSchema(name=type_name))
                types_map[type_name] = new_type.id
            type_id = types_map[type_name]

        # Date: use provided, else today
        date_val = parsed.get("date")
        if not date_val:
            date_val = date_cls.today()

        if existing:
            # Update existing material
            existing.price = parsed["price"]
            existing.date = date_val
            if parsed.get("type_name"):
                existing.type_id = type_id
            if parsed.get("code_1c") and not existing.code_1c:
                existing.code_1c = parsed["code_1c"]
            if parsed.get("code_agent") and not existing.code_agent:
                existing.code_agent = parsed["code_agent"]
            if parsed.get("url_agent") and not existing.url_agent:
                existing.url_agent = parsed["url_agent"]
        else:
            # Create new material
            schema = MaterialCreateSchema(
                name=parsed["name"],
                price=parsed["price"],
                code_1c=parsed.get("code_1c"),
                code_agent=parsed.get("code_agent"),
                url_agent=parsed.get("url_agent"),
                type_id=type_id,
                nom_tok=parsed.get("nom_tok", 0),
                stats=parsed.get("stats", True),
                vtych=parsed.get("vtych", False),
                vykat=parsed.get("vykat", False),
                ruchn=parsed.get("ruchn", True),
                el_priv=parsed.get("el_priv", False),
                date=date_val,
            )
            await crud_materials.add_material(session, schema)
        imported += 1
    return imported


@mat_router.get("/{mat_id}", response_model=MaterialResponseSchema)
async def read_material(mat_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    mat = await crud_materials.get_material_by_id(session=session, mat_id=mat_id)
    if not mat:
        raise HTTPException(status_code=404, detail="Материал не найден")
    return _mat_response(mat)


@mat_router.patch("/", response_model=MaterialResponseSchema)
async def update_material(
    data: MaterialUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_materials.update_material(session=session, upd_mat=data)
    if not result:
        raise HTTPException(status_code=404, detail="Материал не найден")
    await session.commit()
    await session.refresh(result, ["type"])
    return _mat_response(result)


@mat_router.delete("/{mat_id}")
async def delete_material(mat_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    result = await crud_materials.delete_material(session=session, mat_id=mat_id)
    if not result:
        raise HTTPException(status_code=404, detail="Материал не найден")
    await session.commit()
    return {"message": "Материал удалён"}
