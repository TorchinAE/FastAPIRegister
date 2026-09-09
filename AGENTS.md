# AGENTS.md

## Project overview

FastAPI async app for business request management (Russian-language domain). Manages users, directors, positions, organizations, counterparties, requests, invoices, payments, equipment, calculation products, and settings. SQLite via aiosqlite. Jinja2 frontend with HTML/CSS.

## Package manager & setup

- **uv** is the package manager. Use `uv sync` to install, `uv run <cmd>` to execute.
- Python >= 3.12 required (`.python-version` = `3.12`).
- No `uv.lock` in the outer repo — only inside the nested `FastAPIRegister/` submodule copy.
- `.env` must exist with `NAME_BASE=registration` (the DB filename stem). No `.env.example` committed.
- Formatter: `black` (in dependencies, no config file — uses defaults).

## Run & test commands

```bash
uv run uvicorn main:app --reload          # dev server on :8000
uv run pytest                              # run all tests
uv run pytest tests/test_director_routes.py  # single test file
uv run black .                             # format
uv run seed.py                             # seed DB with test data
```

No lint/typecheck tool is configured (no ruff, mypy, or pyright in dependencies).

## Source layout

```
main.py                        # FastAPI app, lifespan creates tables + seeds defaults
config.py                      # pydantic-settings, reads .env → NAME_BASE → sqlite+aiosqlite:///{NAME_BASE}.db
seed.py                        # Standalone seed script (run with `uv run seed.py`)
scr/
  Routers/
    router.py                  # GET / (home page)
    pages.py                   # All page routes (Jinja2 templates)
    auth.py                    # /api/auth (register, login, logout, me)
    directors.py               # /api/directors CRUD
    positions.py               # /api/positions CRUD
    companies.py               # /api/companies CRUD (model is Organization)
    counterparties.py          # /api/counterparties CRUD
    requests.py                # /api/requests CRUD
    equipment.py               # /api/equipment CRUD
    equipment_sections.py      # /api/equipment-sections CRUD
    calc_products.py           # /api/calc-products CRUD (composite products with components)
    calc_items.py              # /api/calc-items CRUD (line items linking requests to products)
    invoices.py                # /api/invoices CRUD
    payments.py                # /api/payments CRUD
    settings.py                # /api/settings CRUD (key-value store)
    users.py                   # /api/users PATCH (user profile update)
  dbase/
    database.py                # DatabaseHelper (engine, session_factory, session_dependency)
    models.py                  # SQLAlchemy models
    schemas/
      schemas.py               # Pydantic schemas (ConfigDict style)
    crud_*.py                  # One CRUD module per entity (13 total)
  queries/                     # Empty directory (unused)
templates/                     # Jinja2 HTML templates (Russian UI)
static/
  style.css
tests/
  conftest.py                  # Async test client, in-memory SQLite override
  test_*.py                    # 14 test files covering most routers
```

## Architecture notes

- **Async SQLAlchemy** throughout. Sessions via `db_helper.session_dependency` (FastAPI Depends).
- **Table creation**: lifespan in `main.py` calls `Base.metadata.create_all` on every startup. Also seeds `Probability` defaults (30%/50%/80%/95%/100%) and `EquipmentSection` defaults.
- **Alembic** is configured for migrations. `env.py` strips `+aiosqlite` to use the sync driver and sets `render_as_batch=True` for SQLite ALTER TABLE support. Commands:
  ```bash
  uv run alembic revision --autogenerate -m "desc"
  uv run alembic upgrade head
  ```
- `BaseID` is the abstract base with `id`, `created_by`, `created_at`, `updated_at`, `changed_by_id` (FK to `users.id`). `User` does NOT inherit `BaseID` — it has its own `id` and `created_at` only.
- API routers all use prefix `/api/...`. Page routes (Jinja2) are in `pages_router` without prefix.
- Auth uses cookie-based sessions (`user_email` cookie). Passwords hashed with bcrypt.
- `Request` has 11 equipment quantity fields (`bktpb`, `ktpb`, `ktp`, `kso_393`, `kso_204`, `k_104`, `k_104m`, `sho`, `pku`, `pus`, `parn`).
- `Invoice` and `PaymentItem` are children of `Request` (cascade delete-orphan).
- `CalcProduct` has `CalcProductComponent` children (cascade delete-orphan). `CalcItem` links a `Request` to a `CalcProduct`.
- `Setting` is a simple key-value store model.
- `calc_products.py` router variable is `cp_router` — same name as counterparties router. Imported in `main.py` as `calc_prod_router` to avoid collision.

## Known issues & gotchas

1. **Explicit `foreign_keys` required**: `Request` has multiple FKs to `users.id`, `organizations.id`, etc. All relationships on `Request` must specify `foreign_keys=[...]` explicitly or SQLAlchemy raises `AmbiguousForeignKeysError`.

2. **Eager loading required**: Async context forbids lazy relationship access. Use `selectinload` (e.g. Directors → Position, CalcProduct → components) or you'll get `MissingGreenlet`.

3. **`.gitignore` excludes `*.md` and `pyproject.toml`** — these files are tracked but listed in gitignore. Force-add (`git add -f`) when adding new `.md` files.

4. **Nested `FastAPIRegister/` directory** is a separate git repo (submodule artifact). It has its own `uv.lock` and slightly different file set. Ignore it for outer-repo work.

5. **`Request.tkp_num`** is NOT auto-generated in CRUD — only `seed.py` sets it manually as `"{id}-{city}"`. If you need auto-generation, add it to the create CRUD function after flush.

6. **Router variable name collision**: `counterparties.py` and `calc_products.py` both export `cp_router`. `main.py` renames the calc one on import.

## Conventions

- CRUD functions follow pattern: `get_X`, `get_X_by_id`, `get_X_by_name`, `add_X`, `update_X`, `delete_X`.
- Duplicate-create returns existing object (no error) — intentional idempotency.
- Schemas use `ConfigDict(from_attributes=True)` (not class-based Config).
- All text is in Russian (comments, descriptions, UI strings). Keep new content consistent.
- Pagination: list endpoints return `PaginatedResponse` with `items`, `total`, `page`, `per_page`, `pages`.
- pytest `asyncio_mode = "auto"` is set in `pyproject.toml` — `@pytest.mark.asyncio` is optional but currently used explicitly in tests.
- Tests use in-memory SQLite and override `db_helper.session_dependency`.
