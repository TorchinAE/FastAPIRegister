from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_users

users_router = APIRouter(prefix="/api/users", tags=["Users"])


class UserUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    signature: Optional[str] = None


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
