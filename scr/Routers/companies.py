from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_organizations
from scr.dbase.schemas.schemas import (
    OrganizationAddSchema,
    OrganizationUpdateSchema,
    OrganizationResponseSchema,
    PaginatedResponse,
)

org_router = APIRouter(prefix="/api/companies", tags=["Companies"])


@org_router.post("/", response_model=OrganizationResponseSchema)
async def add_company(
    company: OrganizationAddSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    new_org = await crud_organizations.add_organization(session=session, in_org=company)
    await session.commit()
    return new_org


@org_router.get("/", response_model=PaginatedResponse)
async def read_companies(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    orgs, total = await crud_organizations.get_organizations(
        session=session, search=search, page=page, per_page=per_page
    )
    return PaginatedResponse(
        items=[OrganizationResponseSchema.model_validate(o) for o in orgs],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@org_router.get("/{org_id}", response_model=OrganizationResponseSchema)
async def read_company(
    org_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    org = await crud_organizations.get_organization_by_id(session=session, org_id=org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return org


@org_router.patch("/", response_model=OrganizationResponseSchema)
async def update_company(
    data: OrganizationUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    result = await crud_organizations.update_organization(
        session=session, update_organization=data
    )
    if not result:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    await session.commit()
    return result


@org_router.delete("/{org_id}")
async def delete_company(
    org_id: int, session: AsyncSession = Depends(db_helper.session_dependency)
):
    result = await crud_organizations.delete_organization(session=session, org_id=org_id)
    if not result:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    await session.commit()
    return {"message": "Компания удалена"}
