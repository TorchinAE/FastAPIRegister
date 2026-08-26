from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.models import EquipmentSection
from scr.dbase.schemas.schemas import EquipmentSectionCreateSchema, EquipmentSectionUpdateSchema


async def get_all_sections(session: AsyncSession, page: int = 1, per_page: int = 20) -> tuple[list[EquipmentSection], int]:
    count_stmt = select(func.count(EquipmentSection.id))
    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = select(EquipmentSection).order_by(EquipmentSection.id).offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_section_by_id(session: AsyncSession, section_id: int) -> EquipmentSection | None:
    return await session.get(EquipmentSection, section_id)


async def add_section(session: AsyncSession, schema: EquipmentSectionCreateSchema, created_by: str = None) -> EquipmentSection:
    section = EquipmentSection(name=schema.name, created_by=created_by)
    session.add(section)
    await session.flush()
    return section


async def update_section(session: AsyncSession, schema: EquipmentSectionUpdateSchema) -> EquipmentSection | None:
    section = await session.get(EquipmentSection, schema.id)
    if not section:
        return None
    data = schema.model_dump(exclude_unset=True, exclude={"id"})
    for key, value in data.items():
        setattr(section, key, value)
    await session.flush()
    return section


async def delete_section(session: AsyncSession, section_id: int) -> EquipmentSection | None:
    section = await session.get(EquipmentSection, section_id)
    if not section:
        return None
    await session.delete(section)
    await session.flush()
    return section
