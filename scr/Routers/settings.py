from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_settings
from pydantic import BaseModel

settings_router = APIRouter(prefix="/api/settings", tags=["Settings"])


class SettingPayload(BaseModel):
    key: str
    value: str


@settings_router.get("/")
async def read_settings(session: AsyncSession = Depends(db_helper.session_dependency)):
    items = await crud_settings.get_all_settings(session)
    return {s.key: s.value for s in items}


@settings_router.put("/")
async def upsert_setting(
    data: SettingPayload,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    await crud_settings.set_setting(session, data.key, data.value)
    await session.commit()
    return {"ok": True}
