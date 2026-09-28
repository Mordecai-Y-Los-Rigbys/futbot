import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.database import engine, Base

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


# Task 0.1: Endpoint de prueba
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Futbot API running"}
