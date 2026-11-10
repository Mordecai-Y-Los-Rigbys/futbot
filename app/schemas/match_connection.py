from typing import Literal

from app.schemas.base import CamelModel


class JoinMatchResponse(CamelModel):
    token_ws: str  # "tokenWs"
    role: Literal["player", "spectator"]
