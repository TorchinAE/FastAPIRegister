# main.py
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from scr.dbase.models import Base

from scr.dbase.database import engine
from scr.Routers.directors import dir_router
from scr.Routers.router import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.connect() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield


app = FastAPI(lifespan=lifespan)
app.include_router(router)
app.include_router(dir_router)


if __name__ == "__main__":
    uvicorn.run("main:app", reload=False)
