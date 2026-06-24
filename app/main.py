from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import appointments, health, lab_tests, patients


def create_app() -> FastAPI:
    app = FastAPI(title="LabLumen appointment-service", version="0.1.0")

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
