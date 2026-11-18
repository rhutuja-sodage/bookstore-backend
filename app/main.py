from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import AsyncMongoClient

from app.config import get_settings
from app.database import ensure_indexes
from app.routers import auth, catalog, orders, reviews
from app.seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client = AsyncMongoClient(settings.mongodb_url, tz_aware=True)
    app.state.db = client[settings.mongodb_db]
    await ensure_indexes(app.state.db)
    if settings.seed_on_startup:
        await seed(app.state.db)
    yield
    await client.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Book Worm API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        await app.state.db.command("ping")
        return {"status": "ok"}

    for module in (auth, catalog, reviews, orders):
        app.include_router(module.router)
    return app


app = create_app()
