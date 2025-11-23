from  fastapi import APIRouter

from scr.dbase.models import Posts, Petitions
from scr.dbase.orm import add_post,  add_petition, \
    add_man_list
from scr.dbase.orm_dir import get_dirs, get_dir_item, add_dir_list, \
    add_director, del_dir, update_dir
from scr.schemas.schemas import DirectorListResponse, DirectorResponseSchema, \
    DirectorAddSchema, DirectorPatch

router = APIRouter()


@router.get("/", description='Главная страница')
async def home():
    return {"message": "home page"}


@router.post("/create_start", description='Создание данных')
async def create_start():
    posts = {'Директор', 'Генеральный директор', 'Исполнительный директор', 'Технический директор', 'Коммерческий директор'}
    for post in posts:
        await add_post(Posts(name=post, directors=[]))

    petitions = {'Ивану Ивановичу', 'Петру Петровичу', 'Сергею Сергеевичу'}
    for petition in petitions:
        await add_petition(Petitions(petition=petition))

    dir_data =[
            {'name':'Иванов Иван Иванович',
            'short_name':'Иванов И.И.',
            'email':'ivanov@ya.ru',
            'phone':'+79991234567',
            'post_id':3,
            'petition_id':1},

            {'name': 'Кубин Петр Петрович',
            'short_name': 'Кубин П.П.',
            'email': 'kubin@rambler.ru',
            'phone': '+79991234765',
            'post_id': 2,
            'petition_id': 2},

            {'name': 'Старин Сергей Сергеевич',
             'short_name': 'Старин С.С.',
             'email': 'starin@mail.ru',
             'phone': '+79991234765',
             'post_id': 1,
             'petition_id': 3}]

    await add_dir_list(dir_data)

    man_data = [{
                    'name':'Pupkin Vasya',
                    'short_name':'Pupkin V.',
                    'email':'d@vri.ru',
                    'phone':'+79991234567'},
                {
                    'name':'Kozin Ilya',
                    'short_name':'KOzin I.',
                    'email':'kozin@vri.ru',
                    'phone':'+79991233333'},
                {
                    'name':'Факир Абдурахманов',
                    'short_name': 'Факир А.',
                    'email': 'fakir@vri.ru',
                    'phone': '+79991244444'},
    ]
    await add_man_list(man_data)


@router.post("/dir", response_model=DirectorResponseSchema, description='Добавление директора')
async def add_dir(director: DirectorAddSchema):
    new_dir = await add_director(**director.model_dump())
    return new_dir


@router.get("/dir", response_model=DirectorListResponse, description='Получение директоров')
async def read_dir():
    directors = await get_dirs()
    return {"directors": directors}


@router.get("/dir/{item}", response_model=DirectorResponseSchema, description='Получение директора по id')
async def read_dir_item(item:int):
    director = await get_dir_item(item)
    return director


@router.delete('/dir/{item}',description='Удаление директора.' )
async def del_dir_item(item:int):
    result = await del_dir(item)
    return result


@router.patch('/dir/{item}',response_model=DirectorResponseSchema, description='Изменение директора.' )
async def update_dir_item(item:int, data_update: DirectorPatch):
    result = await update_dir(item, data_update)
    return result
