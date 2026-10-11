from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import Material, Module, NominalCurrent


async def get_all(session: AsyncSession) -> list[NominalCurrent]:
    result = await session.execute(select(NominalCurrent).order_by(NominalCurrent.value))
    return list(result.scalars().all())


async def get_values(session: AsyncSession) -> list[int]:
    result = await session.execute(select(NominalCurrent.value).order_by(NominalCurrent.value))
    return list(result.scalars().all())


async def ensure_value(session: AsyncSession, value: int) -> NominalCurrent | None:
    """Добавляет значение в справочник, если его нет. 0 означает «нет тока» и не хранится."""
    if not value or value <= 0:
        return None
    result = await session.execute(select(NominalCurrent).where(NominalCurrent.value == value))
    obj = result.scalar_one_or_none()
    if obj:
        return obj
    obj = NominalCurrent(value=value)
    session.add(obj)
    await session.flush()
    return obj


async def sync_from_materials(session: AsyncSession) -> None:
    """Значения ном. тока, уже используемые в материалах и модулях, должны быть в справочнике."""
    for model in (Material, Module):
        result = await session.execute(select(model.nom_tok).where(model.nom_tok > 0).distinct())
        for value in result.scalars().all():
            await ensure_value(session, value)


async def delete(session: AsyncSession, nc_id: int) -> NominalCurrent | None:
    obj = await session.get(NominalCurrent, nc_id)
    if obj:
        await session.delete(obj)
        await session.flush()
    return obj
