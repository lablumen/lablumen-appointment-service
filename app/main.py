from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import appointments, health, lab_tests, patients


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Run any pending migrations before the app starts accepting requests.
    # Alembic holds a Postgres advisory lock on alembic_version, so multiple
    # replicas starting simultaneously are safe — one runs, the rest wait and exit quickly.
    cfg = Config("/app/alembic.ini")
    command.upgrade(cfg, "head")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="LabLumen appointment-service", version="0.1.0", lifespan=lifespan)

    wildcard = settings.cors_origins == ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=not wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(lab_tests.router, prefix="/api/v1")
    app.include_router(appointments.router, prefix="/api/v1")
    app.include_router(patients.router, prefix="/api/v1")
    return app


app = create_app()
