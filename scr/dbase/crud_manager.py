from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession


from scr.dbase.models import Manager
from scr.dbase.schemas.schemas import (
    ManagerUpdateSchema,
    ManagerSchema,
    ManagerCreateSchema,
)


async def get_managers(session: AsyncSession) -> list[Manager]:
    stmt = select(Manager).order_by(Manager.name)
    result: Result = await session.execute(stmt)
    managers = result.scalars().all()
    return list(managers)


async def get_manager_by_id(session: AsyncSession, id: int) -> Manager | None:
    return await session.get(Manager, id)


async def get_manager_by_name(session: AsyncSession, name: str) -> Manager | None:
    stmt = select(Manager).where(Manager.name == name)
    result: Result = await session.execute(stmt)
    manager = result.scalar_one_or_none()
    return manager


async def create_manager(
    session: AsyncSession, new_manager: ManagerCreateSchema
) -> Manager:
    check_manager = await get_manager_by_name(session, new_manager.name)
    if check_manager:
        return check_manager
    new_manager: Manager = Manager(**new_manager.model_dump())
    session.add(new_manager)
    await session.flush()
    return new_manager


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
    await session.delete(manager)
    await session.flush()
    return manager
