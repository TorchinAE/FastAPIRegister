# main.py
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from scr.dbase.database import db_helper
from scr.dbase.models import Base
from scr.Routers.auth import auth_router
from scr.Routers.companies import org_router
from scr.Routers.contract_specs import cs_router
from scr.Routers.counterparties import cp_router
from scr.Routers.deliveries import del_router
from scr.Routers.directors import dir_router
from scr.Routers.equipment import eq_router
from scr.Routers.finance import fin_router
from scr.Routers.invoices import inv_router
from scr.Routers.material_types import mt_router
from scr.Routers.materials import mat_router
from scr.Routers.module_types import mt_calc_router
from scr.Routers.modules import mod_router
from scr.Routers.pages import pages_router
from scr.Routers.payments import pay_router
from scr.Routers.positions import pos_router
from scr.Routers.requests import req_router
from scr.Routers.router import router
from scr.Routers.service_calcs import sc_router
from scr.Routers.settings import settings_router
from scr.Routers.users import users_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with db_helper.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Migrate: add new columns to module_types_calc if missing
    from sqlalchemy import text

    async with db_helper.engine.begin() as conn:
        for col in ("fot_item_id", "overhead_item_id"):
            try:
                await conn.execute(text(f"ALTER TABLE module_types_calc ADD COLUMN {col} INTEGER"))
            except Exception:  # noqa: BLE001, S110
                pass  # column already exists
    # Seed default probabilities
    from sqlalchemy import select

    from scr.dbase.models import DEFAULT_PROBABILITIES, Probability

    async with db_helper.session_factory() as session:
        for id_, name, value in DEFAULT_PROBABILITIES:
            existing = await session.get(Probability, id_)
            if not existing:
                session.add(Probability(id=id_, name=name, value=value))
        await session.commit()
    # Seed default settings
    from scr.dbase.models import Setting

    DEFAULT_SETTINGS = [
        ("smtp_host", ""),
        ("smtp_port", "587"),
        ("smtp_user", ""),
        ("smtp_password", ""),
        ("smtp_from", ""),
        ("adres_server", ""),
        ("tkp_template_folder", ""),
        ("materials_per_page", "30"),
    ]
    async with db_helper.session_factory() as session:
        for key, value in DEFAULT_SETTINGS:
            existing = await session.get(Setting, key)
            if not existing:
                session.add(Setting(key=key, value=value))
        await session.commit()
    # Seed default module types
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    from scr.dbase.models import ModuleType

    DEFAULT_MODULE_TYPES = [
        ("Корпуса", "corpusa"),
        ("КСО", "kso"),
        ("КРУ", "kru"),
        ("ЩО", "sho"),
        ("КТП", "ktp"),
        ("ПКУ", "pku"),
        ("ПУС", "pus"),
        ("Доставка", "delivery"),
        ("Шеф-инженер", "chief-engineer"),
        ("СМР", "smr"),
        ("ПНР", "pnr"),
    ]
    async with db_helper.session_factory() as session:
        result = await session.execute(sa_select(func.count(ModuleType.id)))
        count = result.scalar() or 0
        if count == 0:
            for name, slug in DEFAULT_MODULE_TYPES:
                session.add(ModuleType(name=name, slug=slug))
            await session.commit()
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Static files & templates
import os

static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return HTMLResponse(
        status_code=404,
        content=templates.get_template("404.html").render(request=request),
    )


# API routers
app.include_router(auth_router, prefix="/reg")
app.include_router(router, prefix="/reg")
app.include_router(dir_router, prefix="/reg")
app.include_router(pos_router, prefix="/reg")
app.include_router(org_router, prefix="/reg")
app.include_router(cp_router, prefix="/reg")
app.include_router(req_router, prefix="/reg")
app.include_router(eq_router, prefix="/reg")
app.include_router(inv_router, prefix="/reg")
app.include_router(pay_router, prefix="/reg")
app.include_router(settings_router, prefix="/reg")
app.include_router(users_router, prefix="/reg")
app.include_router(mat_router, prefix="/reg")
app.include_router(mt_router, prefix="/reg")
app.include_router(mt_calc_router, prefix="/reg")
app.include_router(mod_router, prefix="/reg")
app.include_router(del_router, prefix="/reg")
app.include_router(cs_router, prefix="/reg")
app.include_router(sc_router, prefix="/reg")
app.include_router(fin_router, prefix="/reg")
app.include_router(pages_router, prefix="/reg")


if __name__ == "__main__":
    uvicorn.run("main:app", reload=False)
