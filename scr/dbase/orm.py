import logging

from sqlalchemy import select
from fastapi import HTTPException

from scr.dbase.database import async_session
from scr.dbase.models import Manager, Posts, Petitions


async def add_petition(petition: Petitions):
    async with async_session() as session:
        try:
            stmt = select(Petitions).where(Petitions.petition == petition.petition)
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                return  HTTPException(status_code=409, detail='Такое обращение уже существует.')
            session.add(petition)
            await session.commit()
            return HTTPException(status_code=201, detail='Обращение успешно сохранено.')
        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            logging.error(f'Ошибка при сохранении обращения: {e}')
            return HTTPException(status_code=500, detail='ошибка данных при сохранении обращения.')



async def add_post(post: Posts):
    async with async_session() as session:
        try:
            stmt = select(Posts).where(Posts.name == post.name)
            result = await session.execute(stmt)
            if result:
                return  HTTPException(status_code=409, detail='Такой пост уже существует.')
            session.add(post)
            await session.commit()
            return HTTPException(status_code=201, detail='Пост успешно сохранен.')
        except Exception as e:
            await session.rollback()
            logging.ERROR(f'Ошибка при сохранении поста: {e}')
            return HTTPException(status_code=500, detail='ошибка данных при сохранении поста.')



async def add_manager(name: str, short_name: str, email: str, phone: str):
    async with async_session() as session:
        try:
            stmt = select(Manager).where(Manager.name == name)
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                return HTTPException(status_code=409,
                                     detail='Менеджер с таким именем уже существует.')
            manager = Manager(name=name, short_name=short_name, email=email, phone=phone)
            session.add(manager)
            await session.commit()
            await session.refresh(manager)
            return manager

        except HTTPException:
            raise
        except Exception as e:
            await session.rollback()
            logging.error(
                f'Ошибка при сохранении Менеджера {name} {email}: {e}')
            raise HTTPException(status_code=500,
                                detail='Ошибка данных при сохранении Менеджера.')


async def add_man_list(man_list: list[dict]):
    async with async_session() as session:
        try:
            for data in man_list:
                await add_manager(**data)
            return HTTPException(status_code=201, detail='Менеджеры успешно сохранены.')
        except Exception as e:
            await session.rollback()
            logging.error(f'Ошибка при сохранении менеджеров: {e}')
            return HTTPException(status_code=500, detail='Ошибка при сохранении менеджеров')


async def get_manager_by_name(name: str) -> Manager | None:
    async with async_session() as session:
        stmt = select(Manager).where(Manager.name == name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_manager_by_id(id: int) -> Manager | None:
    async with async_session() as session:
        stmt = select(Manager).where(Manager.id == id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()



