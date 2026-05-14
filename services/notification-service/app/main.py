from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from app.db import engine, Base
from app.rabbitmq import start_consumer
from app.routers import notifications

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup crear tablas y lanzar consumidor
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    task = asyncio.create_task(start_consumer())
    yield
    # shutdown cancelar tarea y cerrar conexiones
    task.cancel()
    await engine.dispose()

app = FastAPI(title="Notification Service", lifespan=lifespan)

app.include_router(notifications.router)