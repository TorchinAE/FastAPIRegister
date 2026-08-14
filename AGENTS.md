# AGENTS.md

## Project overview

FastAPI async app for registering business requests (Russian-language domain). Manages managers, directors, positions, organizations, counterparties, and requests. SQLite backend via aiosqlite. Jinja2 frontend with pure HTML/CSS.

## Package manager & setup

- **uv** is the package manager (`uv.lock` present). Use `uv sync` to install, `uv run <cmd>` to execute.
- Python >= 3.12 required.
- `.env` must exist with `NAME_BASE=registration` (the DB filename stem). No `.env.example` committed.
- Formatter: `black` (in dependencies, no config file — uses defaults).

## Run & test commands

```bash
uv run uvicorn main:app --reload          # dev server on :8000
uv run pytest                              # run tests
uv run pytest tests/test_director_routes.py  # single file
uv run black .                             # format
```

No lint/typecheck tool is configured (no ruff, mypy, or pyright in dependencies).

## Source layout

```
main.py                        # FastAPI app, lifespan creates tables, registers all routers
config.py                      # pydantic-settings, reads .env
scr/
  Routers/
    router.py                  # GET / (home page)
    pages.py                   # All page routes (Jinja2 templates)
    auth.py                    # /api/auth (register, login, logout, me)
    directors.py               # /api/directors CRUD
    positions.py               # /api/positions CRUD
    managers.py                # /api/managers CRUD
    companies.py               # /api/companies CRUD
    counterparties.py          # /api/counterparties CRUD
    requests.py                # /api/requests CRUD
    equipment.py               # /api/equipment CRUD
  dbase/
    database.py                # DatabaseHelper, engine, session deps
    models.py                  # SQLAlchemy models (Base, BaseID, User, Manager, Organization, Directors, Positions, Counterparty, Equipment, Request, RequestStatus)
    schemas/
      schemas.py               # Pydantic schemas (ConfigDict style)
    crud_directors.py
    crud_organizations.py
    crud_manager.py
    crud_positions.py
    crud_counterparties.py
    crud_requests.py
    crud_equipment.py
    crud_users.py
templates/                     # Jinja2 HTML templates
  base.html                    # Layout with nav
  login.html, register.html
  dashboard.html
  requests/                    # list, create, detail
  counterparties/, companies/, managers/, directors/, positions/  # list views
static/
  style.css                    # Global styles
tests/
  conftest.py                  # Async test client, in-memory SQLite
  test_director_routes.py
```

## Architecture notes

- **Async SQLAlchemy** throughout. Sessions via `db_helper.session_dependency` (FastAPI Depends).
- **Alembic for migrations** — all schema changes via `uv run alembic revision --autogenerate -m "desc"` then `uv run alembic upgrade head`. No manual SQL or create_all in lifespan.
- `BaseID` is the abstract base with `id`, `created_by`, `created_at`, `updated_at`, `changed_by_id` (FK to managers).
- API routers all use prefix `/api/...`. Page routes (Jinja2) are in `pages_router` without prefix.
- Auth uses cookie-based sessions (`user_email` cookie). Passwords hashed with bcrypt.
- `Request.tkp_num` is auto-generated as `"{id}-{city}"` after flush (needs the ID).
- `Request.company_id` is auto-resolved from `counterparty.company_id`.

## Known issues & gotchas

1. **Duplicate `Base` class**: `scr/dbase/__init__.py` defines its own `Base(DeclarativeBase)` AND re-imports models from `models.py` which also defines `Base`. The app uses `models.py`'s Base. Don't add models to the `__init__.py` Base.

2. **AmbiguousForeignKeysError**: When adding models with FK to `managers.id`, SQLAlchemy gets confused because `BaseID.changed_by_id` also points to `managers.id`. Always specify `foreign_keys=[...]` explicitly on relationships that target `managers`.

3. **Eager loading required**: Directors' `position` relationship must be loaded eagerly (`selectinload`) in async context — lazy access raises `MissingGreenlet`.

4. **Positions field renamed**: `Positions.title` was renamed to `Positions.name` to match MVP spec.

## Conventions

- CRUD functions follow pattern: `get_X`, `get_X_by_id`, `get_X_by_name`, `add_X`, `update_X`, `delete_X`.
- Duplicate-create returns existing object (no error) — this is intentional idempotency.
- Schemas use `ConfigDict(from_attributes=True)` (not class-based Config).
- All text is in Russian (comments, descriptions, UI strings). Keep new content consistent.
- Pagination: all list endpoints return `PaginatedResponse` with `items`, `total`, `page`, `per_page`, `pages`.
