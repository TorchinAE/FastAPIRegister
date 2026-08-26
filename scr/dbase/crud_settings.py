from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.models import Setting


async def get_all_settings(session: AsyncSession) -> list[Setting]:
    result = await session.execute(select(Setting).order_by(Setting.key))
    return list(result.scalars().all())


async def get_setting(session: AsyncSession, key: str) -> str | None:
    setting = await session.get(Setting, key)
    return setting.value if setting else None


async def set_setting(session: AsyncSession, key: str, value: str) -> Setting:
    setting = await session.get(Setting, key)
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        session.add(setting)
    await session.flush()
    return setting


async def delete_setting(session: AsyncSession, key: str) -> bool:
    setting = await session.get(Setting, key)
    if setting:
        await session.delete(setting)
        await session.flush()
        return True
    return False
