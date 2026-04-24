import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.database.connection import init_db
from backend.scheduler.jobs import start_scheduler, stop_scheduler
from backend.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="EasyHome API",
    description="Plataforma de viviendas accesibles para personas con movilidad reducida.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
