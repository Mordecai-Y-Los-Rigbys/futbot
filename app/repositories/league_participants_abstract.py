from dataclasses import dataclass
from typing import Protocol

from app.domain.league import LeagueStatus


@dataclass(frozen=True)
class ParticipantData:
    id: int
    username: str
    club_name: str  # el contrato lo expone como `name` (UserClub)
    avatar: int


@dataclass(frozen=True)
class LeagueParticipantsState:
    """Lo que se envía por /ws/leagues/{id}/participants."""

    status: LeagueStatus
    participants: list[ParticipantData]  # incluido el creador


class LeagueParticipantsRepository(Protocol):
    def get_status(self, league_id: int) -> LeagueStatus | None:
        """Estado de la liga. None si no existe."""
        ...

    def get_state(self, league_id: int) -> LeagueParticipantsState | None:
        """Estado de la liga y sus participantes: el creador primero y el resto
        por id ascendente. None si la liga no existe."""
        ...
