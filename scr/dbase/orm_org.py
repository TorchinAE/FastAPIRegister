import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from scr.dbase.database import async_session
from scr.dbase.models import Organization


async def add_organization(
    name: str, inn: str, address: str, director_id: int, manager_id: int
):
    async with async_session() as session:
        try:
            stmt = select(Organization).where(Organization.name == name)
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=409, detail="Организация с таким именем уже существует."
                )
            organization = Organization(
                name=name,
                inn=inn,
                address=address,
                director_id=director_id,
                manager_id=manager_id,
            )
            session.add(organization)
            await session.commit()
            await session.refresh(organization)

            stmt_full = (
                select(Organization)
                .options(
                    selectinload(Organization.director),
                    selectinload(Organization.manager),
                )
                .where(Organization.id == organization.id)
            )

            result_full = await session.execute(stmt_full)
            full_organization = result_full.scalar_one()

            return full_organization

        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка при сохранении организации {name} {inn}: {e}")
            raise HTTPException(
                status_code=500, detail="Ошибка данных при сохранении организации."
            )


async def add_org_list(org_list: list[dict]):
    async with async_session() as session:
        try:
            for data in org_list:
                await add_organization(**data)
            return HTTPException(
                status_code=201, detail="Организации успешно сохранены."
            )
        except Exception as e:
            await session.rollback()
            logging.error(f"Ошибка при сохранении Организации: {e}")
            return HTTPException(
                status_code=500, detail="Ошибка при сохранении Организации"
            )
