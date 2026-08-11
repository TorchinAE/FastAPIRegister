# main.py
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from scr.dbase.models import Base
from scr.dbase.database import db_helper
from scr.Routers.router import router
from scr.Routers.directors import dir_router
from scr.Routers.positions import pos_router
from scr.Routers.managers import mgr_router
from scr.Routers.companies import org_router
from scr.Routers.counterparties import cp_router
from scr.Routers.requests import req_router
from scr.Routers.auth import auth_router
from scr.Routers.pages import pages_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Tables managed by Alembic. Run: alembic upgrade head
    yield


app = FastAPI(lifespan=lifespan)

# Static files & templates
import os

static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# API routers
app.include_router(auth_router)
app.include_router(router)
app.include_router(dir_router)
app.include_router(pos_router)
app.include_router(mgr_router)
app.include_router(org_router)
app.include_router(cp_router)
app.include_router(req_router)
app.include_router(pages_router)


if __name__ == "__main__":
    uvicorn.run("main:app", reload=False)
