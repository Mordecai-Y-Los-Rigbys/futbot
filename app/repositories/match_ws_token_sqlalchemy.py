from datetime import timezone

from sqlalchemy.orm import Session

from app.models.match_ws_token import MatchWsToken
from app.repositories.match_ws_token_abstract import (
    AbstractMatchWsTokenRepository,
    MatchWsTokenData,
)


class SqlAlchemyMatchWsTokenRepository(AbstractMatchWsTokenRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_token(self, token: str) -> MatchWsTokenData | None:
        record = self.db.get(MatchWsToken, token)
        if record is None:
            return None

        # Las columnas DateTime sin timezone vuelven "naive": se normaliza acá
        # (igual que en el repo de sesiones) para que el servicio compare siempre
        # datetimes con timezone.
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return MatchWsTokenData(
            token=record.token,
            user_id=record.user_id,
            match_id=record.match_id,
            expires_at=expires_at,
        )
