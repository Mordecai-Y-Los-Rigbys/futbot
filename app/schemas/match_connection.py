from app.schemas.base import CamelModel


class JoinMatchResponse(CamelModel):
    token_ws: str  # se serializa como "tokenWs"