import secrets
from datetime import datetime, timedelta, timezone

from app.domain.behavior import BehaviorType
from app.errors import ApiError
from app.repositories.behavior_test_token_abstract import (
    AbstractBehaviorTestTokenRepository,
    CreateBehaviorTestTokenData,
)
from app.services.behavior_service import BehaviorService

BEHAVIOR_TEST_TOKEN_TTL = timedelta(minutes=5)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BehaviorTestConnectionService:
    """Emite los tokens para conectarse a la prueba de un behavior."""

    def __init__(
        self, behaviors: BehaviorService, tokens: AbstractBehaviorTestTokenRepository
    ) -> None:
        self.behaviors = behaviors
        self.tokens = tokens

    def connect(self, user_id: int, behavior_id: int) -> str:
        """Devuelve un tokenWs atado al usuario y al behavior.

        Raises:
            ApiError 404 / 403: los de get_owned_behavior (no existe / es ajeno).
            ApiError 409 notPlayerBehavior: el behavior es de DT.
        """
        behavior = self.behaviors.get_owned_behavior(user_id, behavior_id)
        if behavior.type != BehaviorType.player_behavior:
            raise ApiError(409, "notPlayerBehavior", "Solo se prueban comportamientos de jugador.")

        now = _utcnow()
        token = secrets.token_urlsafe(32)
        self.tokens.create(
            CreateBehaviorTestTokenData(
                token=token,
                user_id=user_id,
                behavior_id=behavior_id,
                created_at=now,
                expires_at=now + BEHAVIOR_TEST_TOKEN_TTL,
            )
        )
        return token