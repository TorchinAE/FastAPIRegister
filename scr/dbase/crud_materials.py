from sqlalchemy import select, Result, func
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import Material
from scr.dbase.schemas.schemas import MaterialCreateSchema, MaterialUpdateSchema


async def get_materials(
    session: AsyncSession, search: str | None = None, page: int = 1, per_page: int = 20
) -> tuple[list[Material], int]:
    stmt = select(Material).order_by(Material.name)
    count_stmt = select(func.count(Material.id))

    if search:
        filter_cond = Material.name.ilike(f"%{search}%")
        stmt = stmt.where(filter_cond)
        count_stmt = count_stmt.where(filter_cond)

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_all_materials(session: AsyncSession) -> list[Material]:
    stmt = select(Material).order_by(Material.name)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_material_by_id(session: AsyncSession, mat_id: int) -> Material | None:
    return await session.get(Material, mat_id)


async def get_material_by_name(session: AsyncSession, name: str) -> Material | None:
    stmt = select(Material).where(Material.name == name)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_material(
    session: AsyncSession, in_mat: MaterialCreateSchema, created_by: str | None = None
) -> Material:
    check_mat = await get_material_by_name(session, in_mat.name)
    if check_mat:
        return check_mat
    mat = Material(**in_mat.model_dump())
    mat.created_by = created_by
    session.add(mat)
    await session.flush()
    return mat


async def update_material(
    session: AsyncSession, upd_mat: MaterialUpdateSchema
) -> Material | None:
    check_mat = await get_material_by_id(session, upd_mat.id)
    if not check_mat:
        return None
    for field, value in upd_mat.model_dump(exclude_unset=True).items():
        if field != "id" and hasattr(check_mat, field):
            setattr(check_mat, field, value)
    await session.flush()
    return check_mat


async def delete_material(session: AsyncSession, mat_id: int) -> Material | None:
    mat = await session.get(Material, mat_id)
    if mat:
        await session.delete(mat)
        await session.flush()
    return mat
