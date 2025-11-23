import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from scr.dbase.database import async_session
from scr.dbase.models import Directors
from scr.schemas.schemas import DirectorPatch


async def add_director(name: str, short_name: str, email: str, phone: str, post_id: int, petition_id: int):
    async with async_session() as session:
        try:
            stmt = select(Directors).where(Directors.name == name)
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                raise HTTPException(status_code=409,
                                     detail='Директор с таким именем уже существует.')
            director = Directors(name=name, short_name=short_name, email=email, phone=phone, post_id=post_id, petition_id=petition_id)
            session.add(director)
            await session.commit()
            await session.refresh(director)

            stmt_full = select(Directors).options(
                selectinload(Directors.post),
                selectinload(Directors.petition)
            ).where(Directors.id == director.id)

            result_full = await session.execute(stmt_full)
            full_director = result_full.scalar_one()

            return full_director


        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            logging.error(
                f'Ошибка при сохранении директора {name} {email}: {e}')
            raise HTTPException(status_code=500,
                                detail='Ошибка данных при сохранении директора.')


async def add_dir_list(dir_list: list[dict]):
    async with async_session() as session:
        try:
            for data in dir_list:
                await add_director(**data)
            return HTTPException(status_code=201, detail='Директора успешно сохранены.')
        except Exception as e:
            await session.rollback()
            logging.error(f'Ошибка при сохранении директоров: {e}')
            return HTTPException(status_code=500, detail='Ошибка при сохранении директоров')


async def get_dirs() -> list[Directors] | list:
    async with async_session() as session:
        stmt = select(Directors)
        result = await session.execute(stmt)
        return result.scalars().all()


async def get_dir_item(item: int) -> Directors | None:
    async with async_session() as session:
        stmt = select(Directors).where(Directors.id==item)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def del_dir(item:int):
    async with async_session() as session:
        stmt =select(Directors).where(Directors.id==item)
        result = await session.execute(stmt)
        director = result.scalar_one_or_none()
        if director:
            await session.delete(director)
            await session.commit()
            return {'message': 'Директор удален.'}
        else:
            raise HTTPException(status_code=404, detail=f"Директор №{item} не найден.")


async def update_dir(director_id: int, update_data: DirectorPatch) -> Directors:
    async with async_session() as session:
        stmt = select(Directors).where(Directors.id == director_id)
        result = await session.execute(stmt)
        existing_dir = result.scalar_one_or_none()

        if not existing_dir:
            raise HTTPException(status_code=404, detail="Директор не найден.")

        for field, value in update_data.model_dump(exclude_unset=True).items():
            if hasattr(existing_dir, field):
                setattr(existing_dir, field, value)

        await session.commit()
        await session.refresh(existing_dir)

        stmt_full = select(Directors).options(
            selectinload(Directors.post),
            selectinload(Directors.petition)
        ).where(Directors.id == existing_dir.id)

        result_full = await session.execute(stmt_full)
        full_director = result_full.scalar_one()

        return full_director