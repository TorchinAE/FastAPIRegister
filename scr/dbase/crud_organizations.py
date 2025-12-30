from tabnanny import check

from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import Organization
from scr.dbase.schemas.schemas import OrganizationAddSchema, OrganizationUpdateSchema


async def get_organizations(session: AsyncSession) -> list[Organization]:
    stmt = select(Organization).order_by(Organization.name)
    result: Result = await session.execute(stmt)
    organizations = result.scalars().all()
    return list(organizations)


async def get_organization_by_id(
    session: AsyncSession, org_id: int
) -> Organization | None:
    stmt = select(Organization).where(Organization.id == org_id)
    result: Result = await session.execute(stmt)
    organization = result.scalar_one_or_none()
    return organization


async def get_organization_by_name(
    session: AsyncSession, name: str
) -> Organization | None:
    stmt = select(Organization).where(Organization.name == name)
    result: Result = await session.execute(stmt)
    organization = result.scalar_one_or_none()
    return organization


async def get_organization_by_inn(
    session: AsyncSession, inn: str
) -> Organization | None:
    stmt = select(Organization).where(Organization.inn == inn)
    result: Result = await session.execute(stmt)
    organization = result.scalar_one_or_none()
    return organization


async def add_organization(
    session: AsyncSession, in_org: OrganizationAddSchema
) -> Organization:
    check_org = await get_organization_by_name(session, name=in_org.name)
    if check_org:
        return check_org
    organization = Organization(**in_org.model_dump())
    session.add(organization)
    await session.flush()
    return organization


async def update_organisation(
    session: AsyncSession, update_organization: OrganizationUpdateSchema
) -> Organization | None:
    check_org = await get_organization_by_id(session, update_organization.id)
    if check_org:
        for field, value in update_organization.model_dump():
            if field != "id" and hasattr(check_org, field):
                setattr(check_org, field, value)
    await session.flush()
    return check_org
