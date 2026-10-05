from collections.abc import Sequence
from typing import Protocol

from app.errors import ApiError


class TeamMemberIds(Protocol):
    """Lo que necesita el chequeo de cada integrante (lo cumple `MemberInput`)."""

    player_id: int
    behavior_id: int


class PlayerOwnership(Protocol):
    def owned_player_ids(self, user_id: int, ids: list[int]) -> set[int]: ...


class BehaviorOwnership(Protocol):
    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]: ...


def ensure_owned_team(
    players: PlayerOwnership,
    behaviors: BehaviorOwnership,
    user_id: int,
    members: Sequence[TeamMemberIds],
) -> None:
    """409 playerOrBehaviorNotOwned si algún jugador o behavior del equipo no
    es del usuario (o no existe: se trata igual para no filtrar qué ids existen)."""
    player_ids = [m.player_id for m in members]
    behavior_ids = list({m.behavior_id for m in members})  # un behavior puede repetirse
    if (
        players.owned_player_ids(user_id, player_ids) != set(player_ids)
        or behaviors.owned_behavior_ids(user_id, behavior_ids) != set(behavior_ids)
    ):
        raise ApiError(
            409,
            "playerOrBehaviorNotOwned",
            "Uno o más jugadores o comportamientos no te pertenecen.",
        )