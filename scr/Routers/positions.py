from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_positions
from scr.dbase.schemas.schemas import (
    PositionCreateSchema,
    PositionUpdateSchema,
    PositionResponseSchema,
    PaginatedResponse,
)

pos_router = APIRouter(prefix="/api/positions", tags=["Positions"])


@pos_router.post("/", response_model=PositionResponseSchema)
async def add_position(
    position: PositionCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new_pos = await crud_positions.add_position(session=session, in_position=position)
    await session.commit()
    return new_pos


@pos_router.get("/", response_model=PaginatedResponse)
async def read_positions(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    positions, total = await crud_positions.get_all_positions(
        session=session, search=search, page=page, per_page=per_page
    )
    return PaginatedResponse(
        items=[PositionResponseSchema.model_validate(p) for p in positions],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@pos_router.get("/{pos_id}", response_model=PositionResponseSchema)
async def read_position(
    pos_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    position = await crud_positions.get_position_id(session=session, pos_id=pos_id)
    if not position:
        raise HTTPException(status_code=404, detail="Должность не найдена")
    return position


@pos_router.patch("/", response_model=PositionResponseSchema)
async def update_position(
    data: PositionUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_positions.update_position(session=session, upd_position=data)
    if not result:
        raise HTTPException(status_code=404, detail="Должность не найдена")
    await session.commit()
    return result


@pos_router.delete("/{pos_id}")
async def delete_position(
    pos_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    result = await crud_positions.delete_position(session=session, pos_id=pos_id)
    if not result:
        raise HTTPException(status_code=404, detail="Должность не найдена")
    await session.commit()
    return {"message": "Должность удалена"}
