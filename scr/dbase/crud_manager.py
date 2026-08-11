from sqlalchemy import select, Result, func
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import Manager
from scr.dbase.schemas.schemas import ManagerUpdateSchema, ManagerCreateSchema


async def get_managers(
    session: AsyncSession, search: str | None = None, page: int = 1, per_page: int = 20
) -> tuple[list[Manager], int]:
    stmt = select(Manager).order_by(Manager.name)
    count_stmt = select(func.count(Manager.id))

    if search:
        filter_cond = Manager.name.ilike(f"%{search}%") | Manager.email.ilike(f"%{search}%")
        stmt = stmt.where(filter_cond)
        count_stmt = count_stmt.where(filter_cond)

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_manager_by_id(session: AsyncSession, id: int) -> Manager | None:
    return await session.get(Manager, id)


async def get_manager_by_name(session: AsyncSession, name: str) -> Manager | None:
    stmt = select(Manager).where(Manager.name == name)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_manager(
    session: AsyncSession, new_manager: ManagerCreateSchema, created_by: str | None = None
) -> Manager:
    check_manager = await get_manager_by_name(session, new_manager.name)
    if check_manager:
        return check_manager
    manager = Manager(**new_manager.model_dump())
    manager.created_by = created_by
    session.add(manager)
    await session.flush()
    return manager


async def update_manager(
    session: AsyncSession, manager: ManagerUpdateSchema
) -> Manager | None:
    upd_manager = await get_manager_by_id(session, manager.id)
    if not upd_manager:
        return None
    for field, value in manager.model_dump(exclude_unset=True).items():
        if field != "id" and hasattr(upd_manager, field):
            setattr(upd_manager, field, value)
    await session.flush()
    return upd_manager


async def delete_manager(session: AsyncSession, manager_id: int) -> Manager | None:
    manager = await session.get(Manager, manager_id)
    if manager:
        await session.delete(manager)
        await session.flush()
    return manager
