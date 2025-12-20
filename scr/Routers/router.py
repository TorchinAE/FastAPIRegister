from fastapi import APIRouter, HTTPException

from scr.dbase.models import Posts, Petitions
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
    posts = {
        "Директор",
        "Генеральный директор",
        "Исполнительный директор",
        "Технический директор",
        "Коммерческий директор",
    }
    for post in posts:
        try:
            await add_post(Posts(name=post, directors=[]))
        except HTTPException as e:
            if e.status_code == 409:
                print(f"Пост '{post}' уже существует, пропускаем.")
            else:
                raise

    petitions = {"Ивану Ивановичу", "Петру Петровичу", "Сергею Сергеевичу"}
    for petition in petitions:
        await add_petition(Petitions(petition=petition))

    dir_data = [
        {
            "name": "Иванов Иван Иванович",
            "short_name": "Иванов И.И.",
            "email": "ivanov@ya.ru",
            "phone": "+79991234567",
            "post_id": 3,
            "petition_id": 1,
        },
        {
            "name": "Кубин Петр Петрович",
            "short_name": "Кубин П.П.",
            "email": "kubin@rambler.ru",
            "phone": "+79991234765",
            "post_id": 2,
            "petition_id": 2,
        },
        {
            "name": "Старин Сергей Сергеевич",
            "short_name": "Старин С.С.",
            "email": "starin@mail.ru",
            "phone": "+79991234765",
            "post_id": 1,
            "petition_id": 3,
        },
    ]

    await add_dir_list(dir_data)

    man_data = [
        {
            "name": "Pupkin Vasya",
            "short_name": "Pupkin V.",
            "email": "d@vri.ru",
            "phone": "+79991234567",
        },
        {
            "name": "Kozin Ilya",
            "short_name": "KOzin I.",
            "email": "kozin@vri.ru",
            "phone": "+79991233333",
        },
        {
            "name": "Факир Абдурахманов",
            "short_name": "Факир А.",
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
