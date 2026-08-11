from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_manager
from scr.dbase.schemas.schemas import (
    ManagerCreateSchema,
    ManagerUpdateSchema,
    ManagerResponseSchema,
    PaginatedResponse,
)

mgr_router = APIRouter(prefix="/api/managers", tags=["Managers"])


@mgr_router.post("/", response_model=ManagerResponseSchema)
async def add_manager(
    manager: ManagerCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new_mgr = await crud_manager.add_manager(session=session, new_manager=manager)
    await session.commit()
    return new_mgr


@mgr_router.get("/", response_model=PaginatedResponse)
async def read_managers(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    managers, total = await crud_manager.get_managers(
        session=session, search=search, page=page, per_page=per_page
    )
    return PaginatedResponse(
        items=[ManagerResponseSchema.model_validate(m) for m in managers],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@mgr_router.get("/{mgr_id}", response_model=ManagerResponseSchema)
async def read_manager(
    mgr_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    manager = await crud_manager.get_manager_by_id(session=session, id=mgr_id)
    if not manager:
        raise HTTPException(status_code=404, detail="Менеджер не найден")
    return manager


@mgr_router.patch("/", response_model=ManagerResponseSchema)
async def update_manager(
    data: ManagerUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_manager.update_manager(session=session, manager=data)
    if not result:
        raise HTTPException(status_code=404, detail="Менеджер не найден")
    await session.commit()
    return result


@mgr_router.delete("/{mgr_id}")
async def delete_manager(
    mgr_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    result = await crud_manager.delete_manager(session=session, manager_id=mgr_id)
    if not result:
        raise HTTPException(status_code=404, detail="Менеджер не найден")
    await session.commit()
    return {"message": "Менеджер удален"}
