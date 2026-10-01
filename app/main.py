import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app import models  # noqa: F401  (registra los modelos en Base.metadata)
from app.api import auth
from app.api.leagues import router as leagues_router
from app.api.behaviors import router as behaviors_router
from app.database import Base, engine
from app.errors import (
    ApiError,
    api_error_handler,
    register_validation_exception_handler,
)

load_dotenv()

# Crea las tablas en la BD (para desarrollo temprano, luego usarás Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Futbot API")

# Routeamos auth
app.include_router(auth.router)
app.include_router(leagues_router)
app.include_router(behaviors_router)
app.add_exception_handler(
    RequestValidationError, register_validation_exception_handler
)

# Task 0.2: Configuración de CORS
origins = [
    os.getenv("FRONTEND_URL", "http://localhost:3000"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Vital para que viajen las cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)


# Task 0.1: Endpoint de prueba
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Futbot API running"}