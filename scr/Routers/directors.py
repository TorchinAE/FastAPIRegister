from fastapi import APIRouter

from scr.dbase.orm_dir import get_dirs, get_dir_item, add_director, del_dir, update_dir
from scr.dbase.schemas import (
    DirectorResponseSchema,
    DirectorAddSchema,
    DirectorListResponse,
    DirectorPatch,
)

dir_router = APIRouter(prefix="/directors", tags=["Directors"])


@dir_router.post(
    "/", response_model=DirectorResponseSchema, description="Добавление директора"
)
async def add_dir(director: DirectorAddSchema):
    new_dir = await add_director(**director.model_dump())
    return new_dir


@dir_router.get(
    "/", response_model=DirectorListResponse, description="Получение директоров"
)
async def read_dir():
    directors = await get_dirs()
    return {"directors": directors}


@dir_router.get(
    "/{item}",
    response_model=DirectorResponseSchema,
    description="Получение директора по id",
)
async def read_dir_item(item: int):
    director = await get_dir_item(item)
    return director


@dir_router.delete("/{item}", description="Удаление директора.")
async def del_dir_item(item: int):
    result = await del_dir(item)
    return result


@dir_router.patch(
    "/{item}", response_model=DirectorResponseSchema, description="Изменение директора."
)
async def update_dir_item(item: int, data_update: DirectorPatch):
    result = await update_dir(item, data_update)
    return result
