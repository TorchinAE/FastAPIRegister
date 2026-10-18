from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scr.constants import DEFAULT_UNIT
from scr.dbase.models import Material, Unit


async def get_all(session: AsyncSession) -> list[Unit]:
    result = await session.execute(select(Unit).order_by(Unit.id))
    return list(result.scalars().all())


async def get_names(session: AsyncSession) -> list[str]:
    result = await session.execute(select(Unit.name).order_by(Unit.id))
    return list(result.scalars().all())


async def ensure_name(session: AsyncSession, name: str | None) -> Unit | None:
    """Добавляет единицу измерения в справочник, если её нет."""
    name = (name or "").strip()
    if not name:
        return None
    result = await session.execute(select(Unit).where(Unit.name == name))
    obj = result.scalar_one_or_none()
    if obj:
        return obj
    obj = Unit(name=name)
    session.add(obj)
    await session.flush()
    return obj


async def sync_from_materials(session: AsyncSession) -> None:
    """Единицы, уже используемые в материалах, должны быть в справочнике."""
    result = await session.execute(select(Material.unit).distinct())
    for name in result.scalars().all():
        await ensure_name(session, name)


async def delete(session: AsyncSession, unit_id: int) -> Unit | None:
    obj = await session.get(Unit, unit_id)
    if obj and obj.name != DEFAULT_UNIT:
        await session.delete(obj)
        await session.flush()
    return obj
