from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.database import Base, engine
from app.routes import app_router
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("MAIN_SECRET_KEY")

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.include_router(app_router)
app.mount("/static", StaticFiles(directory="templates/static"), name="static")