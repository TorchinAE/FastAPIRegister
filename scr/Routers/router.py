from fastapi import APIRouter, HTTPException

from scr.dbase.models import Positions, NamePetitions, PatronymicPetitions
from scr.dbase.orm import add_post, add_petition, add_man_list
from scr.dbase.orm_dir import (
    get_dirs,
    get_dir_item,
    add_dir_list,
    add_director,
    del_dir,
    update_dir,
)
from scr.dbase.orm_org import add_org_list


router = APIRouter()


@router.get("/", description="Главная страница")
async def home():
    return {"message": "home page"}


@router.post("/create_start", description="Создание данных")
async def create_start():
    titles = {
        "Директор",
        "Генеральный директор",
        "Исполнительный директор",
        "Технический директор",
        "Коммерческий директор",
    }
    for title in titles:
        try:
            await add_post(Positions(title=title, directors=[]))
        except HTTPException as e:
            if e.status_code == 409:
                print(f"Должность '{title}' уже существует, пропускаем.")
            else:
                raise

    dir_data = [
        {
            "name": "Иванов Иван Иванович",
            "email": "ivanov@ya.ru",
            "phone": "+79991234567",
            "post_id": 3,
        },
        {
            "name": "Кубин Петр Петрович",
            "email": "kubin@rambler.ru",
            "phone": "+79991234765",
            "post_id": 2,
        },
        {
            "name": "Старин Сергей Сергеевич",
            "email": "starin@mail.ru",
            "phone": "+79991234765",
            "post_id": 1,
        },
    ]

    await add_dir_list(dir_data)

    man_data = [
        {
            "name": "Pupkin Vasya",
            "email": "d@vri.ru",
            "phone": "+79991234567",
        },
        {
            "name": "Kozin Ilya",
            "email": "kozin@vri.ru",
            "phone": "+79991233333",
        },
        {
            "name": "Факир Абдурахманов",
            "email": "fakir@vri.ru",
            "phone": "+79991244444",
        },
    ]
    await add_man_list(man_data)

    organizations = [
        {
            "name": "ООО Рога и копыта",
            "inn": "37120522",
            "address": "Дальние дали д.12",
            "director_id": 2,
            "manager_id": 2,
        },
        {
            "name": "ООО Батерфляй",
            "inn": "331234651234",
            "address": "На деревню деушке д.7 корп  2",
            "director_id": 1,
            "manager_id": 3,
        },
        {
            "name": "ИП Пузякин",
            "inn": "3334566234",
            "address": "Прямо и направо д.11/6",
            "director_id": 3,
            "manager_id": 1,
        },
    ]
    await add_org_list(man_data)
