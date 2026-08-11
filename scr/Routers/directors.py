from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_directors
from scr.dbase.schemas.schemas import (
    DirectorSchema,
    DirectorResponseSchema,
    DirectorUpdateSchema,
    PaginatedResponse,
)

dir_router = APIRouter(prefix="/api/directors", tags=["Directors"])


@dir_router.post("/", response_model=DirectorResponseSchema)
async def add_dir(
    director: DirectorSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new_dir = await crud_directors.add_dir(session=session, dir_in=director)
    if new_dir:
        await session.commit()
        await session.refresh(new_dir, ["position"])
        return new_dir
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)


@dir_router.get("/", response_model=PaginatedResponse)
async def read_dirs(
    position_id: int | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    directors, total = await crud_directors.get_dirs(
        session=session, position_id=position_id, search=search, page=page, per_page=per_page
    )
    return PaginatedResponse(
        items=[DirectorResponseSchema.model_validate(d) for d in directors],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@dir_router.get("/{dir_id}", response_model=DirectorResponseSchema)
async def read_dir_item(
    dir_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    director = await crud_directors.get_dir_to_id(session=session, dir_id=dir_id)
    if not director:
        raise HTTPException(status_code=404, detail="Директор не найден")
    return director


@dir_router.patch("/", response_model=DirectorResponseSchema)
async def update_dir_item(
    data_update: DirectorUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_directors.update_dir(session=session, upd_dir=data_update)
    if not result:
        raise HTTPException(status_code=404, detail="Директор не найден")
    await session.commit()
    await session.refresh(result, ["position"])
    return result


@dir_router.delete("/{dir_id}")
async def delete_dir_item(
    dir_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    result = await crud_directors.delete_dir(session=session, dir_id=dir_id)
    if not result:
        raise HTTPException(status_code=404, detail="Директор не найден")
    await session.commit()
    return {"message": "Директор удален"}
