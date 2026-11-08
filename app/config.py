import os


def allowed_origins() -> list[str]:
    """Orígenes permitidos para CORS y para el header `Origin` de los WebSocket.

    `ALLOWED_ORIGINS` (separados por coma) o, si no está, `FRONTEND_URL`.
    """
    raw = os.getenv("ALLOWED_ORIGINS") or os.getenv("FRONTEND_URL", "http://localhost:5173")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
