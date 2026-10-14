from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import AccuracyClass, Material


async def get_all(session: AsyncSession) -> list[AccuracyClass]:
    result = await session.execute(select(AccuracyClass).order_by(AccuracyClass.id))
    return list(result.scalars().all())


async def get_names(session: AsyncSession) -> list[str]:
    result = await session.execute(select(AccuracyClass.name).order_by(AccuracyClass.id))
    return list(result.scalars().all())


async def ensure_name(session: AsyncSession, name: str | None) -> AccuracyClass | None:
    """Добавляет класс точности в справочник, если его нет. Пустое значение — класс не задан."""
    name = (name or "").strip()
    if not name:
        return None
    result = await session.execute(select(AccuracyClass).where(AccuracyClass.name == name))
    obj = result.scalar_one_or_none()
    if obj:
        return obj
    obj = AccuracyClass(name=name)
    session.add(obj)
    await session.flush()
    return obj


async def sync_from_materials(session: AsyncSession) -> None:
    """Классы точности, уже используемые в материалах, должны быть в справочнике."""
    result = await session.execute(
        select(Material.accuracy_class).where(Material.accuracy_class.is_not(None)).distinct()
    )
    for name in result.scalars().all():
        await ensure_name(session, name)


async def delete(session: AsyncSession, class_id: int) -> AccuracyClass | None:
    obj = await session.get(AccuracyClass, class_id)
    if obj:
        await session.delete(obj)
        await session.flush()
    return obj
