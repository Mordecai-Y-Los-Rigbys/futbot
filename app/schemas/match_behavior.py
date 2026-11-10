from app.schemas.base import CamelModel


class MatchPlayerBehavior(CamelModel):
    """Respuesta de GET /matches/{id}/behavior: nombre y código del behavior
    que tiene asignado un titular del usuario en este momento."""

    name: str
    code: str
