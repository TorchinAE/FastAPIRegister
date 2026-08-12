from sqlalchemy import select, Result, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase.models import Organization
from scr.dbase.schemas.schemas import OrganizationAddSchema, OrganizationUpdateSchema


async def get_organizations(
    session: AsyncSession,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Organization], int]:
    stmt = select(Organization).options(selectinload(Organization.director)).order_by(Organization.id)
    count_stmt = select(func.count(Organization.id))

    if search:
        filter_cond = Organization.name.ilike(f"%{search}%") | Organization.inn.ilike(f"%{search}%")
        stmt = stmt.where(filter_cond)
        count_stmt = count_stmt.where(filter_cond)

    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_organization_by_id(
    session: AsyncSession, org_id: int
) -> Organization | None:
    return await session.get(Organization, org_id)


async def get_organization_by_name(
    session: AsyncSession, name: str
) -> Organization | None:
    stmt = select(Organization).where(Organization.name == name)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_organization(
    session: AsyncSession, in_org: OrganizationAddSchema, created_by: str | None = None
) -> Organization:
    check_org = await get_organization_by_name(session, name=in_org.name)
    if check_org:
        return check_org
    organization = Organization(**in_org.model_dump())
    organization.created_by = created_by
    session.add(organization)
    await session.flush()
    return organization


async def update_organization(
    session: AsyncSession, update_organization: OrganizationUpdateSchema
) -> Organization | None:
    check_org = await get_organization_by_id(session, update_organization.id)
    if not check_org:
        return None
    for field, value in update_organization.model_dump(exclude_unset=True).items():
        if field != "id" and hasattr(check_org, field):
            setattr(check_org, field, value)
    await session.flush()
    return check_org


async def delete_organization(session: AsyncSession, org_id: int) -> Organization | None:
    org = await session.get(Organization, org_id)
    if org:
        await session.delete(org)
        await session.flush()
    return org
