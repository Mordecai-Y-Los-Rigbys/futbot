import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.domain.behavior import BehaviorType
from app.errors import ApiError
from app.repositories.behavior_abstract import AbstractBehaviorRepository
from app.repositories.behavior_test_token_abstract import (
    AbstractBehaviorTestTokenRepository,
    BehaviorTestMemberData,
    CreateBehaviorTestTokenData,
)
from app.repositories.player_abstract import AbstractPlayerRepository
from app.services.behavior_test_validation import parse_behavior_test
from app.services.team_ownership import ensure_owned_typed_team

BEHAVIOR_TEST_TOKEN_TTL = timedelta(minutes=5)
BEHAVIOR_NOT_FOUND_MESSAGE = "Comportamiento no encontrado."


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BehaviorTestConnectionService:
    """Emite los tokens para conectarse a la prueba de un behavior."""

    def __init__(
        self,
        behaviors: AbstractBehaviorRepository,
        players: AbstractPlayerRepository,
        tokens: AbstractBehaviorTestTokenRepository,
    ) -> None:
        self.behaviors = behaviors
        self.players = players
        self.tokens = tokens

    def connect(self, user_id: int, behavior_id: int, body: Any) -> str:
        """Devuelve un tokenWs atado al usuario, al behavior y a la alineación.

        Orden: 404 > 400 > 403 > 409. El 404 y el 403 se evalúan por separado
        porque la validación del body va entre los dos.

        Raises:
            ApiError 404: el behavior no existe.
            ValidationApiError 400: invalidFields, con todos los campos que fallan.
            ApiError 403: el behavior es de otro usuario.
            ApiError 409: notPlayerBehavior, playerOrBehaviorNotOwned o
                behaviorTypeMismatch, en ese orden.
        """
        behavior = self.behaviors.get_by_id(behavior_id)
        if behavior is None:
            raise ApiError(404, None, BEHAVIOR_NOT_FOUND_MESSAGE)

        members = parse_behavior_test(body)

        if behavior.user_id != user_id:
            raise ApiError(403, None, "El comportamiento no pertenece al usuario.")
        if behavior.type != BehaviorType.player_behavior:
            raise ApiError(409, "notPlayerBehavior", "Solo se prueban comportamientos de jugador.")
        ensure_owned_typed_team(self.players, self.behaviors, user_id, members, None)

        now = _utcnow()
        token = secrets.token_urlsafe(32)
        self.tokens.create(
            CreateBehaviorTestTokenData(
                token=token,
                user_id=user_id,
                behavior_id=behavior_id,
                created_at=now,
                expires_at=now + BEHAVIOR_TEST_TOKEN_TTL,
                members=[
                    BehaviorTestMemberData(
                        player_id=m.player_id,
                        club=m.club,
                        role=m.role,
                        behavior_id=m.behavior_id,
                    )
                    for m in members
                ],
            )
        )
        return token
