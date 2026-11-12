import re

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import AccuracyClass, Material


def normalize(name: str | None) -> str:
    """Класс точности как в справочнике: без пробелов по краям, десятичная запятая (0.5S → 0,5S)."""
    return (name or "").strip().replace(".", ",")


def natural_key(name: str) -> tuple:
    """Порядок по возрастанию с учётом чисел: 0,2 < 0,2S < 0,5 < 1 < 3 < 5P < 10P."""
    parts = re.split(r"(\d+(?:,\d+)?)", name or "")
    return tuple(
        (0, float(p.replace(",", ".")), "") if i % 2 else (1, 0.0, p.lower()) for i, p in enumerate(parts) if p
    )


async def get_all(session: AsyncSession) -> list[AccuracyClass]:
    result = await session.execute(select(AccuracyClass))
    return sorted(result.scalars().all(), key=lambda c: natural_key(c.name))


async def get_names(session: AsyncSession) -> list[str]:
    result = await session.execute(select(AccuracyClass.name))
    return sorted(result.scalars().all(), key=natural_key)


async def get_by_name(session: AsyncSession, name: str) -> AccuracyClass | None:
    result = await session.execute(select(AccuracyClass).where(AccuracyClass.name == name))
    return result.scalar_one_or_none()


async def ensure_name(session: AsyncSession, name: str | None) -> AccuracyClass | None:
    """Добавляет класс точности в справочник, если его нет. Пустое значение — класс не задан."""
    name = normalize(name)
    if not name:
        return None
    obj = await get_by_name(session, name)
    if obj:
        return obj
    obj = AccuracyClass(name=name)
    session.add(obj)
    await session.flush()
    return obj


async def rename(session: AsyncSession, obj: AccuracyClass, new_name: str) -> AccuracyClass:
    """Переименование класса; материалы получают новое значение.
    Такой класс уже есть — классы объединяются (остаётся существующий)."""
    new_name = normalize(new_name)
    old_name = obj.name
    if not new_name or new_name == old_name:
        return obj
    await session.execute(update(Material).where(Material.accuracy_class == old_name).values(accuracy_class=new_name))
    existing = await get_by_name(session, new_name)
    if existing and existing.id != obj.id:
        await session.delete(obj)
        await session.flush()
        return existing
    obj.name = new_name
    await session.flush()
    return obj


async def normalize_existing(session: AsyncSession) -> None:
    """Точки в классах точности (справочник и материалы) заменяются на запятые."""
    for obj in [c for c in await get_all(session) if "." in c.name]:
        await rename(session, obj, obj.name)
    result = await session.execute(
        select(Material.accuracy_class).where(Material.accuracy_class.like("%.%")).distinct()
    )
    for name in result.scalars().all():
        await session.execute(
            update(Material).where(Material.accuracy_class == name).values(accuracy_class=normalize(name))
        )
    await session.flush()


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
