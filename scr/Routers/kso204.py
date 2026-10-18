"""Выгрузка расчёта КСО в КСО204-ткп{№ ТКП}.xlsx и варианты расчёта ТКП."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_kso204, crud_requests
from scr.dbase.database import db_helper
from scr.utils.kso204 import kso204_filename

kso_router = APIRouter(prefix="/api/requests", tags=["KSO204"])

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class LoadVariantSchema(BaseModel):
    # Перед переходом сохранить текущий вариант в его файл
    save_current: bool = True


async def _request_or_404(session: AsyncSession, req_id: int):
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="ТКП не найдена")
    return req


@kso_router.get("/{req_id}/kso204/export-excel")
async def download_kso204(req_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    """Файл КСО204 по текущему расчёту КСО — скачать, без сохранения в папку ТКП."""
    req = await _request_or_404(session, req_id)
    try:
        data, _ = await crud_kso204.build_request_kso204(session, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    filename = kso204_filename(req.tkp_num or str(req.id))
    return Response(
        data, media_type=XLSX_TYPE, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    )


@kso_router.post("/{req_id}/kso204/save")
async def save_kso204(req_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    """Сохраняет расчёт КСО в папку ТКП: КСО204-ткп{№ ТКП}.xlsx (файл перезаписывается)."""
    req = await _request_or_404(session, req_id)
    try:
        path, warnings = await crud_kso204.save_request_kso204(session, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить файл: {exc}") from exc
    await session.commit()
    return {"filename": path.name, "path": str(path), "warnings": warnings}


@kso_router.get("/{req_id}/variants")
async def list_variants(req_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    req = await _request_or_404(session, req_id)
    try:
        return await crud_kso204.list_variants(session, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@kso_router.post("/{req_id}/variants")
async def create_variant(req_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    """+Вариант: текущий расчёт сохраняется в файл, номер ТКП → следующий вариант (8-ив → 8-2ив → 8-3ив)."""
    req = await _request_or_404(session, req_id)
    try:
        path, warnings = await crud_kso204.new_variant(session, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось сохранить файл: {exc}") from exc
    await session.commit()
    return {"tkp_num": req.tkp_num, "saved": path.name, "warnings": warnings}


@kso_router.post("/{req_id}/variants/{n}/load")
async def load_variant(
    req_id: int,
    n: int,
    data: LoadVariantSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    """Переход к варианту n: расчёт КСО загружается из файла варианта, номер ТКП — номер варианта."""
    req = await _request_or_404(session, req_id)
    try:
        warnings = await crud_kso204.load_variant(session, req, n, data.save_current)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла варианта: {exc}") from exc
    tkp_num = req.tkp_num
    await session.commit()
    return {"tkp_num": tkp_num, "warnings": warnings}
