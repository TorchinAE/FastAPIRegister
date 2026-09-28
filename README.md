# FastAPIRegister

Система регистрации и управления заявками на электрооборудование. Async FastAPI + SQLite + Jinja2.

## Стек

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), aiosqlite
- **Frontend:** Jinja2, HTML/CSS
- **БД:** SQLite (alembic для миграций)
- **Пакетный менеджер:** uv
- **Линтер/форматтер:** ruff
- **Тесты:** pytest, pytest-asyncio, httpx

## Запуск локально

```bash
# Установка зависимостей
uv sync

# Создать .env
echo "NAME_BASE=registration" > .env

# Запуск dev-сервера
uv run uvicorn main:app --reload
```

Сервер на `http://127.0.0.1:8000/reg/`

## Тесты

```bash
uv run pytest                           # все тесты
uv run pytest tests/test_director_routes.py  # один файл
uv run pytest --cov=scr --cov-report=term-missing  # с покрытием
```

## Форматирование и линтинг

```bash
uv run ruff format .    # форматирование
uv run ruff check .     # линтинг
uv run ruff check . --fix  # автоисправление
```

## Структура проекта

```
main.py                          # Точка входа, lifespan, подключение роутеров
config.py                        # Настройки (pydantic-settings, .env)
FastAPIRegister.service          # Systemd unit файл
seed.py                          # Наполнение БД тестовыми данными

scr/
  Routers/
    auth.py                      # Регистрация, вход, выход
    pages.py                     # Jinja2 страницы
    requests.py                  # CRUD заявок
    companies.py                 # CRUD организаций
    counterparties.py            # CRUD контрагентов
    directors.py                 # CRUD директоров
    positions.py                 # CRUD должностей
    equipment.py                 # CRUD оборудования
    materials.py                 # CRUD материалов
    modules.py                   # CRUD модулей
    invoices.py                  # CRUD счетов
    payments.py                  # CRUD платежей
    users.py                     # Профиль пользователя
    settings.py                  # Настройки
  dbase/
    models.py                    # SQLAlchemy модели
    schemas/schemas.py           # Pydantic схемы
    database.py                  # Движок, сессии
    crud_*.py                    # Функции CRUD

templates/                       # Jinja2 шаблоны
static/                          # CSS, статика
tests/                           # Тесты (pytest)
alembic/                         # Миграции БД
```

## Деплой

CI/CD через GitHub Actions автоматически при пуше в `main`:

1. **Lint** — ruff format + ruff check
2. **Test** — pytest с coverage
3. **Deploy** — SSH на сервер, `uv sync`, рестарт systemd сервиса

### Необходимые GitHub Secrets

| Secret | Описание |
|---|---|
| `DEPLOY_HOST` | IP/домен сервера |
| `DEPLOY_USER` | SSH пользователь (`root`) |
| `DEPLOY_SSH_KEY` | Приватный SSH ключ (ed25519) |
| `REG_SECRET_KEY` | Секретный ключ приложения |
| `REG_ADMIN_USERNAME` | Логин администратора |
| `REG_ADMIN_PASSWORD` | Пароль администратора |

### Ручной деплой

```bash
cd /root/FastAPIRegister
git pull origin main
uv sync
sudo cp FastAPIRegister.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart FastAPIRegister
```

## Тестовые данные

```bash
uv run python seed.py
```

Загружает: 3 пользователя, 4 должности, 4 директора, 4 организации, 5 контрагентов, 6 заявок.

Тестовые логины: `ivan@test.ru`, `maria@test.ru`, `sidorov@company.ru` (пароль: `123456`)

## Архитектурные решения

- Все роуты приложения префиксованы `/reg/`
- Health check деплоя стучится на `/reg/` (не `/`)
- SQLite файл: `registration.db` (имя из `NAME_BASE` в `.env`)
- Systemd сервис перезапускается автоматически (`Restart=always`)
- Nginx проксирует `/reg/` → `127.0.0.1:8000`, `/quiz/` → `127.0.0.1:8080`
