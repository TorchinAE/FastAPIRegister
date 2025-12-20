from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import Petitions


class CrudPetition:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_by_petition(self, petition: str) -> Petitions | None:
        stat = select(Petitions).where(Petitions.petition == petition)
        result = await self.session.execute(stat)
        return result.scalar_one_or_none()

    async def create_petition(self, petition: str) -> Petitions:
        check_petition = await self._get_by_petition(petition)
        if check_petition:
            return check_petition
        new_petition = Petitions(petition=petition)
        self.session.add(new_petition)
        await self.session.flush()
        return new_petition
