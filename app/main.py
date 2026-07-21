from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.config import get_settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title=get_settings().app_name,
    version="0.1.0",
    description="Backend-first portfolio project for deterministic invoice and receipt intake, review, and audit.",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health", tags=["operations"])
def health():
    return {"status": "ok"}

