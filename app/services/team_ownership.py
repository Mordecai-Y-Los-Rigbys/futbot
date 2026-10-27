from collections.abc import Sequence
from typing import Protocol

from app.domain.behavior import BehaviorType
from app.errors import ApiError


class TeamMemberIds(Protocol):
    """Lo que necesita el chequeo de cada integrante (lo cumple `MemberInput`)."""

    player_id: int
    behavior_id: int


class PlayerOwnership(Protocol):
    def owned_player_ids(self, user_id: int, ids: list[int]) -> set[int]: ...


class BehaviorOwnership(Protocol):
    def owned_behavior_ids(self, user_id: int, ids: list[int]) -> set[int]: ...


class TypedBehaviorOwnership(Protocol):
    def behavior_types(self, user_id: int, ids: list[int]) -> dict[int, BehaviorType]: ...


def _not_owned() -> ApiError:
    return ApiError(
        409,
        "playerOrBehaviorNotOwned",
        "Uno o más jugadores o comportamientos no te pertenecen.",
    )


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
    if players.owned_player_ids(user_id, player_ids) != set(
        player_ids
    ) or behaviors.owned_behavior_ids(user_id, behavior_ids) != set(behavior_ids):
        raise _not_owned()


def ensure_owned_typed_team(
    players: PlayerOwnership,
    behaviors: TypedBehaviorOwnership,
    user_id: int,
    members: Sequence[TeamMemberIds],
    coach_behavior_id: int | None,
) -> None:
    """Convención 10: pertenencia y tipo de los behaviors del equipo y del DT.

    Raises:
        ApiError 409 playerOrBehaviorNotOwned: algún jugador, behavior de
            `members` o el DT no es del usuario o no existe (se evalúa primero).
        ApiError 409 behaviorTypeMismatch: todos son del usuario, pero algún
            behavior de `members` no es playerBehavior o el DT no es coachBehavior.
    """
    player_ids = [m.player_id for m in members]
    wanted = {m.behavior_id for m in members}  # un behavior puede repetirse
    if coach_behavior_id is not None:
        wanted.add(coach_behavior_id)

    owned_players = players.owned_player_ids(user_id, player_ids)
    types = behaviors.behavior_types(user_id, sorted(wanted))
    if owned_players != set(player_ids) or set(types) != wanted:
        raise _not_owned()

    wrong_member = any(types[m.behavior_id] != BehaviorType.player_behavior for m in members)
    wrong_coach = (
        coach_behavior_id is not None and types[coach_behavior_id] != BehaviorType.coach_behavior
    )
    if wrong_member or wrong_coach:
        raise ApiError(
            409,
            "behaviorTypeMismatch",
            "Los jugadores necesitan behaviors de jugador y el DT un behavior de DT.",
        )
