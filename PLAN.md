# План реализации MVP

## Решения
- **БД**: SQLite (оставляем как есть)
- **Фронт**: Jinja2 + FastAPI, чистый HTML/CSS, без JS-фреймворков
- **Авторизация**: полная — регистрация, хеширование паролей (bcrypt), сессии через cookies

---

## Фаза 0: Исправление багов и очистка ✅
- [x] `crud_positions.py` — удалить мусорные импорты (`black.cache`, `horizontal_shard`)
- [x] `crud_organizations.py` — удалить `from tabnanny import check`
- [x] `directors.py` роутер — исправить вызов `add_dir` (kwargs → schema object)
- [x] `conftest.py` — исправить импорт несуществующего `create_db_and_tables`
- [x] Тесты — обновить пути роутов (`/dir` → `/directors/`) и поля запросов
- [x] Исправить `AmbiguousForeignKeysError` — явные `foreign_keys` в relationship

## Фаза 1: Модели (models.py) ✅
- [x] `Positions` — переименовать `title` → `name`
- [x] `Manager` — добавить `city: str` (default "ив")
- [x] `Organization` — добавить `server_address_slug` (default "/02_сторонние_заказчики")
- [x] Новая модель `Counterparty` — name, email (unique), phone, company_id FK
- [x] Новая модель `Request` — counterparty_id FK, company_id FK, manager_id FK, request_date, status (enum), description, notes, tkp_num, 11 полей оборудования (0-100), created_by
- [x] `BaseID` — добавить `created_by: str` (nullable)
- [x] Enum `RequestStatus` — 7 значений
- [x] Модель `User` — name, email, hashed_password

## Фаза 2: Схемы (schemas.py) ✅
- [x] Обновить все схемы (ConfigDict вместо class Config)
- [x] Новые схемы: Counterparty, Request, User, PaginatedResponse
- [x] Валидация оборудования 0-100 через Field(ge=0, le=100)

## Фаза 3: CRUD функции ✅
- [x] `crud_positions.py` — обновлен (name, пагинация, поиск)
- [x] `crud_manager.py` — обновлен (city, пагинация, поиск)
- [x] `crud_organizations.py` — обновлен (server_address_slug, пагинация, поиск)
- [x] `crud_directors.py` — обновлен (пагинация, поиск, eager-load position)
- [x] Новый `crud_counterparties.py`
- [x] Новый `crud_requests.py` — с автозаполнением company_id и tkp_num
- [x] Новый `crud_users.py` — bcrypt хеширование

## Фаза 4: Роутеры (API endpoints) ✅
- [x] `directors.py` — `/api/directors` CRUD + фильтры + пагинация
- [x] `positions.py` — `/api/positions` CRUD
- [x] `managers.py` — `/api/managers` CRUD + поиск
- [x] `companies.py` — `/api/companies` CRUD + поиск
- [x] `counterparties.py` — `/api/counterparties` CRUD + фильтр company_id
- [x] `requests.py` — `/api/requests` CRUD + все фильтры
- [x] `auth.py` — register, login, logout, me (cookies)
- [x] `main.py` — все роутеры зарегистрированы

## Фаза 5: Авторизация ✅
- [x] Модель `User` — name, email, hashed_password
- [x] Хеширование паролей — bcrypt
- [x] Cookies-based сессии
- [x] Фронтенд: форма логина/регистрации

## Фаза 6: Фронтенд (Jinja2 шаблоны) ✅
- [x] Базовый шаблон (`base.html`) — навигация, responsive CSS
- [x] Страница входа (`/`) + регистрация
- [x] Дашборд (`/dashboard`) — последние 15 запросов
- [x] Список запросов (`/requests`) с пагинацией
- [x] Создание запроса (`/requests/create`)
- [x] Детали запроса (`/requests/{id}`)
- [x] Списки: контрагенты, компании, менеджеры, директора, должности
- [x] `pages_router` — все страницы зарегистрированы

## Фаза 7: Тесты ✅
- [x] `conftest.py` — async test client, in-memory SQLite
- [x] Базовые тесты: home, positions CRUD, directors CRUD
