from dotenv import load_dotenv
from collections.abc import AsyncIterator
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
from app.api.ws_leagues import router as ws_leagues_router
from app.api.ws_notifications import router as ws_notifications_router
from app.api.friendlies import router as friendlies_router
from app.api.ws_deps import (
    get_friendly_expiry,
    get_friendly_start,
    get_league_match_start,
    get_match_runner,
)
from app.api.matches import router as matches_router
from app.api.ranking import router as ranking_router
from app.api.users import router as users_router

from app.config import allowed_origins
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
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    expiry = get_friendly_expiry()
    start = get_friendly_start()
    league_start = get_league_match_start()
    await expiry.recover()
    await start.recover()
    await league_start.recover()
    yield
    league_start.shutdown()
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
app.include_router(ws_leagues_router)
app.include_router(ws_notifications_router)
app.include_router(friendlies_router)
app.include_router(matches_router)
app.include_router(ranking_router)
app.include_router(users_router)


# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
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
