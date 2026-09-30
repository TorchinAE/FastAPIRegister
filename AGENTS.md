# AGENTS.md

## Project overview

FastAPI async app for registering business requests on electrical equipment (Russian-language domain). SQLite via aiosqlite. Jinja2 frontend with pure HTML/CSS. Deployed to a VPS behind nginx.

## Commands

```bash
uv sync                                       # install deps
uv run uvicorn main:app --reload              # dev server on :8000, serves /reg/
uv run pytest                                 # all tests (asyncio_mode = "auto")
uv run pytest tests/test_director_routes.py   # single file
uv run pytest --cov=scr --cov-report=term-missing  # with coverage
uv run ruff format .                          # format
uv run ruff check . --fix                     # lint + auto-fix
uv run python seed.py                         # seed test data (3 users, 4 positions, etc.)
uv run alembic revision --autogenerate -m "desc"  # generate migration
uv run alembic upgrade head                   # apply migrations
```

## Setup

- **uv** is the package manager. Python >= 3.12.
- `.env` must exist with `NAME_BASE=registration` (DB filename stem). CI creates it automatically.
- Linter/formatter: **ruff** (`line-length=120`, ignores `B008`, `F401`, `DTZ005` in `pyproject.toml`).
- CI runs: lint (`ruff format --check` + `ruff check`) -> test (`pytest --cov`) -> deploy (SSH + systemd restart). Deploys only on push to `main`.

## Source layout

```
main.py                     # App entrypoint, lifespan creates tables + seeds Probability defaults
config.py                   # pydantic-settings reads .env (NAME_BASE, REG_SECRET_KEY, admin creds)
seed.py                     # Standalone script to populate DB with test data
scr/
  Routers/                  # All API routers mounted at /reg/api/...; page routes at /reg/...
    auth.py                 # /api/auth (register, login, logout, me)
    pages.py                # Jinja2 page routes
    directors.py, positions.py, companies.py, counterparties.py,
    requests.py, equipment.py, managers.py, users.py,
    invoices.py, payments.py, materials.py, material_types.py,
    modules.py, settings.py
  dbase/
    database.py             # DatabaseHelper, engine, session_dependency
    models.py               # All SQLAlchemy models
    schemas/schemas.py      # All Pydantic schemas (ConfigDict style)
    crud_*.py               # One CRUD module per entity
  queries/                  # Empty directory (unused)
tests/
  conftest.py               # In-memory SQLite, overrides session_dependency
  test_director_routes.py, test_excel.py, test_material_routes.py, test_module_routes.py
templates/                  # Jinja2 HTML
static/                     # CSS
alembic/                    # Migrations
```

## Architecture

- **Async SQLAlchemy** throughout. Sessions via `db_helper.session_dependency` (FastAPI `Depends`).
- **All routes are prefixed `/reg`** in `main.py` (not `/api` directly). So the actual URL is `/reg/api/...` for API and `/reg/...` for pages. Nginx proxies `/reg/` -> `:8000`.
- **Table creation**: lifespan calls `Base.metadata.create_all` + seeds `Probability` defaults on every startup.
- Alembic's `env.py` uses sync driver (strips `+aiosqlite`) and `render_as_batch=True` for SQLite ALTER TABLE.
- `BaseID` abstract base: `id`, `created_by`, `created_at`, `updated_at`, `changed_by_id` (FK to `users.id`).
- Auth: cookie-based sessions (`user_email` cookie). Passwords hashed with bcrypt.
- `Request.tkp_num` is auto-generated as `"{id}-{city}"` after flush.
- `Request.company_id` is auto-resolved from `counterparty.company_id`.
- Materials and Modules routers include Excel import/export via openpyxl.
- Lifespan also seeds a `Probability` table with 5 default rows (30%, 50%, 80%, 95%, 100%).

## Model gotchas

- **`BaseID.changed_by_id` FK points to `users.id`**, not `managers`. The old `managers` table was renamed to `users`. When adding relationships that reference users, you may need explicit `foreign_keys=[...]` to avoid ambiguity with `changed_by_id`.
- **Eager loading required**: `Directors.position` must be loaded eagerly (`selectinload`) in async context — lazy raises `MissingGreenlet`.
- **ModuleItem** has a CHECK constraint: exactly one of `material_id` or `sub_module_id` must be non-null (not both, not neither). `Module.total_price` recurses into sub-modules.
- **Request** has many optional date/number fields for tracking invoices, factory orders, shipping, and cost — see `models.py` for the full set.
- `Organization.director_id` is NOT nullable (required FK), unlike the MVP spec which made it optional.

## Conventions

- CRUD functions: `get_X`, `get_X_by_id`, `get_X_by_name`, `add_X`, `update_X`, `delete_X`. Duplicate-create returns existing object (idempotent).
- Schemas: `ConfigDict(from_attributes=True)` on `BaseSchema`, inherited by most response schemas.
- All text is in Russian (comments, UI strings, enum values). Keep new content consistent.
- Pagination: list endpoints return `PaginatedResponse` with `items`, `total`, `page`, `per_page`, `pages`.
- pytest `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio` decorator.
- Tests use in-memory SQLite with `dependency_overrides` — no real DB needed.
- Ruff ignores: `B008` (Depends in function args), `F401` (unused imports), `DTZ005` (datetime.utcnow).