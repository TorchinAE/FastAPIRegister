from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import Organization
from scr.dbase.schemas.schemas import OrganizationAddSchema


async def get_organizations(session: AsyncSession) -> list[Organization]:
    stat = select(Organization).order_by(Organization.name)
    result: Result = await session.execute(stat)
    organizations = result.scalars().all()
    return list(organizations)


async def get_organization_by_id(
    session: AsyncSession, org_id: int
) -> Organization | None:
    stat = select(Organization).where(Organization.id == org_id)
    result: Result = await session.execute(stat)
    organization = result.scalar_one_or_none()
    return organization


async def get_organization_by_name(
    session: AsyncSession, name: str
) -> Organization | None:
    stat = select(Organization).where(Organization.name == name)
    result: Result = await session.execute(stat)
    organization = result.scalar_one_or_none()
    return organization


async def get_organization_by_inn(
    session: AsyncSession, inn: str
) -> Organization | None:
    stat = select(Organization).where(Organization.inn == inn)
    result: Result = await session.execute(stat)
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
