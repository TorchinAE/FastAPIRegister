# main.py
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from scr.dbase.database import db_helper
from scr.dbase.models import Base
from scr.Routers.accuracy_classes import ac_router
from scr.Routers.auth import auth_router
from scr.Routers.companies import org_router
from scr.Routers.contract_specs import cs_router
from scr.Routers.counterparties import cp_router
from scr.Routers.deliveries import del_router
from scr.Routers.directors import dir_router
from scr.Routers.equipment import eq_router
from scr.Routers.finance import fin_router
from scr.Routers.invoices import inv_router
from scr.Routers.kso204 import kso_router
from scr.Routers.material_types import mt_router
from scr.Routers.materials import mat_router
from scr.Routers.module_types import mt_calc_router
from scr.Routers.modules import mod_router
from scr.Routers.nominal_currents import nc_router
from scr.Routers.pages import pages_router
from scr.Routers.payments import pay_router
from scr.Routers.positions import pos_router
from scr.Routers.requests import req_router
from scr.Routers.router import router
from scr.Routers.service_calcs import sc_router
from scr.Routers.settings import settings_router
from scr.Routers.units import units_router
from scr.Routers.users import users_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with db_helper.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Migrate: add missing columns, drop obsolete ones
    from scr.dbase.startup_migrations import run_startup_migrations

    async with db_helper.engine.begin() as conn:
        await run_startup_migrations(conn)
    # Seed default probabilities
    from sqlalchemy import select

    from scr.constants import DEFAULT_PROBABILITIES
    from scr.dbase.models import Probability

    async with db_helper.session_factory() as session:
        for id_, name, value in DEFAULT_PROBABILITIES:
            existing = await session.get(Probability, id_)
            if not existing:
                session.add(Probability(id=id_, name=name, value=value))
        await session.commit()
    # Seed default settings
    from scr.constants import DEFAULT_K_FOT, DEFAULT_K_NAKL, SETTING_CONTRACT_FOLDER, SETTING_K_FOT, SETTING_K_NAKL
    from scr.dbase.models import Setting

    DEFAULT_SETTINGS = [
        ("smtp_host", ""),
        ("smtp_port", "587"),
        ("smtp_user", ""),
        ("smtp_password", ""),
        ("smtp_from", ""),
        ("adres_server", ""),
        ("tkp_template_folder", ""),
        (SETTING_CONTRACT_FOLDER, ""),
        ("materials_per_page", "30"),
        ("nds_percent", "20"),
        # Коэффициенты ФОТ и накладных для расчёта КСО204 (лист «расчет», строки 41 и 40)
        (SETTING_K_FOT, str(DEFAULT_K_FOT)),
        (SETTING_K_NAKL, str(DEFAULT_K_NAKL)),
    ]
    async with db_helper.session_factory() as session:
        for key, value in DEFAULT_SETTINGS:
            existing = await session.get(Setting, key)
            if not existing:
                session.add(Setting(key=key, value=value))
        await session.commit()
    # Seed default module types
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
        ("Силовой трансформатор", "power-transformer"),
        ("Монтаж оборудования в блоки", "mounting"),
    ]
    async with db_helper.session_factory() as session:
        # Недостающие разделы (новые добавляются и в существующую базу)
        existing = set((await session.execute(sa_select(ModuleType.slug))).scalars().all())
        for name, slug in DEFAULT_MODULE_TYPES:
            if slug not in existing:
                session.add(ModuleType(name=name, slug=slug))
        await session.commit()
    # Seed nominal currents: standard values + values already used in materials
    from scr.constants import DEFAULT_NOMINAL_CURRENTS
    from scr.dbase import crud_nominal_currents

    async with db_helper.session_factory() as session:
        if not await crud_nominal_currents.get_values(session):
            for value in DEFAULT_NOMINAL_CURRENTS:
                await crud_nominal_currents.ensure_value(session, value)
        await crud_nominal_currents.sync_from_materials(session)
        await session.commit()
    # Seed units of measure: defaults + units already used in materials
    from scr.constants import DEFAULT_UNITS
    from scr.dbase import crud_units

    async with db_helper.session_factory() as session:
        if not await crud_units.get_names(session):
            for name in DEFAULT_UNITS:
                await crud_units.ensure_name(session, name)
        await crud_units.sync_from_materials(session)
        await session.commit()
    # Seed accuracy classes: defaults + classes already used in materials
    from scr.constants import DEFAULT_ACCURACY_CLASSES
    from scr.dbase import crud_accuracy_classes

    async with db_helper.session_factory() as session:
        if not await crud_accuracy_classes.get_names(session):
            for name in DEFAULT_ACCURACY_CLASSES:
                await crud_accuracy_classes.ensure_name(session, name)
        await crud_accuracy_classes.sync_from_materials(session)
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
templates.env.globals["static_v"] = int(os.path.getmtime(os.path.join(static_dir, "style.css")))


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
app.include_router(nc_router, prefix="/reg")
app.include_router(units_router, prefix="/reg")
app.include_router(ac_router, prefix="/reg")
app.include_router(del_router, prefix="/reg")
app.include_router(cs_router, prefix="/reg")
app.include_router(sc_router, prefix="/reg")
app.include_router(fin_router, prefix="/reg")
app.include_router(kso_router, prefix="/reg")
app.include_router(pages_router, prefix="/reg")


if __name__ == "__main__":
    uvicorn.run("main:app", reload=False)
