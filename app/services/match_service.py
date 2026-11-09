from app.domain.match import MatchStatus
from app.domain.team_member import MemberRole
from app.errors import ApiError
from app.repositories.match_abstract import (
    AbstractMatchRepository,
    MatchDetailData,
    PenaltyShootoutData,
)
from app.repositories.team_abstract import AbstractTeamRepository, LineupPlayerData
from app.schemas.friendly import MatchResponse
from app.schemas.lineup import LineupPlayer, MatchLineups
from app.services.friendly_service import to_match_club
from app.services.league_access_service import LeagueAccessService

MATCH_NOT_FOUND_MESSAGE = "El partido no existe."
# Orden de los titulares en MatchLineups.
LINEUP_ORDER = (MemberRole.forward, MemberRole.midfield, MemberRole.defense)


def _penalties(shootout: PenaltyShootoutData | None) -> dict | None:
    if shootout is None:
        return None
    return {
        "score1": shootout.score_1,
        "score2": shootout.score_2,
        "winner": "club1" if shootout.winner == 1 else "club2",
        "kicks": shootout.kicks,
    }


def _result(match: MatchDetailData) -> dict | None:
    if match.status != MatchStatus.finished:
        return None
    return {
        "score1": match.score_1,
        "score2": match.score_2,
        "penalties": _penalties(match.penalties),
    }


def _to_response(match: MatchDetailData) -> MatchResponse:
    return MatchResponse(
        id=match.id,
        league_id=match.league_id,
        name=match.name,
        status=match.status.value,
        club1=to_match_club(match.club1),
        club2=to_match_club(match.club2) if match.club2 is not None else None,
        scheduled_at=match.scheduled_at,
        created_at=match.created_at,
        result=_result(match),
    )


def _to_lineup(players: list[LineupPlayerData]) -> list[LineupPlayer]:
    by_role = sorted(players, key=lambda player: LINEUP_ORDER.index(player.role))
    return [
        LineupPlayer(player_id=player.player_id, name=player.name, role=player.role.value)
        for player in by_role
    ]


def _is_player(match: MatchDetailData, user_id: int) -> bool:
    return match.club1.id == user_id or (match.club2 is not None and match.club2.id == user_id)


class MatchService:
    """Consultas de partidos."""

    def __init__(
        self,
        matches: AbstractMatchRepository,
        league_access: LeagueAccessService,
        teams: AbstractTeamRepository,
    ) -> None:
        self.matches = matches
        self.league_access = league_access
        self.teams = teams

    def get_match(self, match_id: int, session_id: str, user_id: int) -> MatchResponse:
        """Partido de liga o amistoso, en cualquier estado.

        Raises:
            ApiError 404: el partido no existe.
            ApiError 403 notAPlayerInMatch: amistoso y el usuario no es jugador.
            ApiError 403 leagueAccessRequired: liga privada sin acceso.
        """
        return _to_response(self._get_visible(match_id, session_id, user_id))

    def get_lineups(self, match_id: int, session_id: int, user_id: int) -> MatchLineups:
        """Titulares de ambos clubes.

        Raises:
            ApiError 404: el partido no existe.
            ApiError 403 notAPlayerInMatch: amistoso y el usuario no es jugador.
            ApiError 403 leagueAccessRequired: liga privada sin acceso.
        """
        match = self._get_visible(match_id, session_id, user_id)
        club1 = self._lineup(match, match.club1.id)
        club2 = self._lineup(match, match.club2.id) if match.club2 is not None else None
        return MatchLineups(club1=club1, club2=club2)

    def _lineup(self, match: MatchDetailData, user_id: int) -> list[LineupPlayer]:
        return _to_lineup(self.teams.get_lineup(match.id, match.league_id, user_id))

    def _get_visible(self, match_id: int, session_id: str, user_id: int) -> MatchDetailData:
        """El partido, si el usuario lo puede ver."""
        match = self.matches.get_detail(match_id)
        if match is None:
            raise ApiError(404, None, MATCH_NOT_FOUND_MESSAGE)
        if not _is_player(match, user_id):
            self._require_spectator_access(match, session_id, user_id)
        return match

    def _require_spectator_access(
        self, match: MatchDetailData, session_id: str, user_id: int
    ) -> None:
        if match.league is None:
            raise ApiError(403, "notAPlayerInMatch", "Un amistoso solo lo ven sus jugadores.")
        self.league_access.require_access(session_id, user_id, match.league)
