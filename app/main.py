import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.database import engine, Base
from app.errors import ApiError, api_error_handler
from app import models  # noqa: F401  (registra los modelos en Base.metadata)
from app.api.behaviors import router as behaviors_router

load_dotenv()

# Crea las tablas en la BD (para desarrollo temprano, luego usarás Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Futbot API")

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
app.include_router(behaviors_router)


# Task 0.1: Endpoint de prueba
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Futbot API running"}
