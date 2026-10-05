import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registra los modelos en Base.metadata)
from app.api.auth import router as auth_router
from app.api.behaviors import router as behaviors_router
from app.api.leagues import router as leagues_router
from app.api.players import router as players_router
from app.api.ws_matches import router as ws_matches_router
from app.api.friendlies import router as friendlies_router
from app.api.ws_deps import get_friendly_expiry, get_friendly_start, get_match_runner
from app.api.matches import router as matches_router
from app.api.users import router as users_router

from app.database import Base, engine
from app.errors import (
    ApiError,
    api_error_handler,
    validation_exception_handler,
)
from app.startup_checks import ensure_single_worker

load_dotenv()
ensure_single_worker()

# Crea las tablas en la BD (para desarrollo temprano, luego usarás Alembic)
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    expiry = get_friendly_expiry()
    await expiry.recover()
    yield
    start.shutdown()
    await get_match_runner().shutdown()
    expiry.shutdown()

app = FastAPI(title="Futbot API", lifespan=lifespan)

# Routeamos auth
app.include_router(auth_router)
app.include_router(players_router)
app.include_router(behaviors_router)
app.include_router(leagues_router)
app.include_router(ws_matches_router)
app.include_router(friendlies_router)
app.include_router(matches_router)
app.include_router(users_router)



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
app.add_exception_handler(RequestValidationError, validation_exception_handler)


# Task 0.1: Endpoint de prueba
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Futbot API running"}