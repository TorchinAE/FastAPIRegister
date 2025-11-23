import asyncio

import uvicorn
from fastapi import FastAPI
from watchfiles import awatch

from scr.Routers.router import router
from scr.dbase.database import create_db_and_tables

app =FastAPI()


app.include_router(router)

if __name__ == "__main__":
    asyncio.run(create_db_and_tables())
    uvicorn.run("main:app", reload=False)
