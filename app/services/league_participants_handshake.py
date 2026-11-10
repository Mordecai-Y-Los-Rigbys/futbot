from collections.abc import Collection

from app.domain.league import LeagueStatus
from app.errors import ApiError
from app.repositories.league_access_abstract import LeagueAccessRepository
from app.repositories.league_participants_abstract import LeagueParticipantsRepository
from app.services.league_channel_handshake import LeagueChannelHandshakeService, ValidSessions


def reject_unless_preparation(status: LeagueStatus | None) -> ApiError | None:
    if status != LeagueStatus.preparation:
        return ApiError(409, "leagueNotInPreparation", "La liga ya no está en preparación.")
    return None


class LeagueParticipantsHandshakeService(LeagueChannelHandshakeService):
    """Valida el handshake de /ws/leagues/{id}/participants: solo en preparation."""

    def __init__(
        self,
        allowed_origins: Collection[str],
        sessions: ValidSessions,
        access: LeagueAccessRepository,
        participants: LeagueParticipantsRepository,
    ) -> None:
        super().__init__(
            allowed_origins, sessions, access, participants, reject_unless_preparation
        )
