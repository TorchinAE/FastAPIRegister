from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_users
from scr.dbase.database import db_helper
from scr.dbase.models import (
    ContractSpec,
    Counterparty,
    Delivery,
    Directors,
    Equipment,
    Invoice,
    Material,
    MaterialType,
    Module,
    Organization,
    PaymentItem,
    Positions,
    Request,
    User,
)

users_router = APIRouter(prefix="/api/users", tags=["Users"])


class UserUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str | None = None
    email: str | None = None
    city: str | None = None
    signature: str | None = None


@users_router.patch("/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdate,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_users.update_user(session, user_id, **data.model_dump(exclude={"id"}))
    if not result:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    await session.commit()
    return {"ok": True}


@users_router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    reassign_to: int,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    target = await crud_users.get_user_by_id(session, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    reassign_user = await crud_users.get_user_by_id(session, reassign_to)
    if not reassign_user:
        raise HTTPException(status_code=404, detail="Пользователь для переназначения не найден")
    if user_id == reassign_to:
        raise HTTPException(status_code=400, detail="Нельзя переназначить на того же пользователя")

    # Reassign Request.manager_id (NOT NULL)
    await session.execute(update(Request).where(Request.manager_id == user_id).values(manager_id=reassign_to))
    # NULL out changed_by_id on all tables that have it
    for model in [
        Organization,
        Directors,
        Positions,
        Counterparty,
        Equipment,
        Invoice,
        PaymentItem,
        Delivery,
        ContractSpec,
        Material,
        MaterialType,
        Module,
    ]:
        await session.execute(update(model).where(model.changed_by_id == user_id).values(changed_by_id=None))

    result = await crud_users.delete_user(session, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    await session.commit()
    return {"ok": True}
