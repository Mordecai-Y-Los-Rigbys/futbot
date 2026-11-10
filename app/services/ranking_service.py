from app.domain.league import LeagueStatus
from app.errors import ApiError
from app.repositories.ranking_abstract import AbstractRankingRepository, ClubRankingData
from app.schemas.ranking import GlobalRankingEntry, GlobalRankingPage, LeagueRankingEntry

PAGE_SIZE = 50
POINTS_WIN = 3
POINTS_WIN_PENALTIES = 2
POINTS_DRAW = 1


def _score(club: ClubRankingData) -> int:
    return (
        POINTS_WIN * club.won_regular
        + POINTS_WIN_PENALTIES * club.won_penalties
        + POINTS_DRAW * club.drawn
    )


def _criteria(club: ClubRankingData) -> tuple[int, int, int, int, int, int]:
    """Los seis criterios, en orden de prioridad. Dos clubes con la misma tupla
    están empatados (comparten puesto)."""
    return (
        -_score(club),
        -(club.goals_for - club.goals_against),
        -club.goals_for,
        -club.won_regular,
        -club.won_penalties,
        club.lost,  # ascendente: el que perdió menos va más arriba
    )


def _rank(clubs: list[ClubRankingData]) -> list[tuple[int, ClubRankingData]]:
    """Ordena por los seis criterios y devuelve (position, club). Los empatados
    en todo comparten puesto (1, 2, 2, 4) y se ordenan por id de club."""
    ordered = sorted(clubs, key=lambda club: (*_criteria(club), club.club_id))
    ranked: list[tuple[int, ClubRankingData]] = []
    position = 0
    previous: tuple | None = None
    for index, club in enumerate(ordered, start=1):
        criteria = _criteria(club)
        if criteria != previous:
            position, previous = index, criteria
        ranked.append((position, club))
    return ranked


def to_league_ranking(clubs: list[ClubRankingData]) -> list[LeagueRankingEntry]:
    """Ordena y mapea los totales de los participantes al schema LeagueRanking."""
    return [
        LeagueRankingEntry(
            position=position,
            name=club.name,
            avatar=club.avatar,
            played=club.won_regular + club.won_penalties + club.drawn + club.lost,
            won_regular=club.won_regular,
            won_penalties=club.won_penalties,
            drawn=club.drawn,
            lost=club.lost,
            goals=club.goals_for,
            goal_difference=club.goals_for - club.goals_against,
            score=_score(club),
        )
        for position, club in _rank(clubs)
    ]


class RankingService:
    """Ranking global y ranking de liga."""

    def __init__(self, repo: AbstractRankingRepository) -> None:
        self.repo = repo

    def get_global_ranking(self, page: int, name: str | None) -> GlobalRankingPage:
        """Ranking de los clubes con partidos finalizados en ligas públicas.

        `position` se calcula sobre el ranking completo, antes de filtrar por
        `name` y paginar.
        """
        entries = [
            GlobalRankingEntry(
                position=position,
                name=club.name,
                avatar=club.avatar,
                score=_score(club),
                goal_difference=club.goals_for - club.goals_against,
                goals=club.goals_for,
                won_regular=club.won_regular,
                won_penalties=club.won_penalties,
                lost=club.lost,
            )
            for position, club in _rank(self.repo.list_club_totals())
        ]

        if name:  # "" se trata como ausente
            needle = name.lower()
            entries = [entry for entry in entries if needle in entry.name.lower()]

        offset = (page - 1) * PAGE_SIZE
        return GlobalRankingPage(
            items=entries[offset : offset + PAGE_SIZE],
            page=page,
            page_size=PAGE_SIZE,
            total=len(entries),
        )

    def get_league_ranking(self, league_id: int) -> list[LeagueRankingEntry]:
        """Llamar después de validar existencia y acceso a la liga."""
        status = self.repo.get_league_status(league_id)
        if status == LeagueStatus.preparation:
            raise ApiError(409, "leagueNotStarted", "La liga todavía no fue iniciada.")
        if status == LeagueStatus.cancelled:
            raise ApiError(409, "leagueCancelled", "La liga fue cancelada.")

        return to_league_ranking(self.repo.list_league_club_totals(league_id))
