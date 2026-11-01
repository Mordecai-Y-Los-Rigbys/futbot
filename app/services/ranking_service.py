from app.repositories.ranking_abstract import AbstractRankingRepository, ClubRankingData
from app.schemas.ranking import GlobalRankingEntry, GlobalRankingPage

PAGE_SIZE = 50
POINTS_WIN = 3
POINTS_WIN_PENALTIES = 2
POINTS_DRAW = 1


def _score(c: ClubRankingData) -> int:
    return (
        POINTS_WIN * c.won_regular + POINTS_WIN_PENALTIES * c.won_penalties + POINTS_DRAW * c.drawn
    )


def _criteria(c: ClubRankingData) -> tuple[int, int, int, int, int, int]:
    """Los seis criterios, en orden de prioridad. Dos clubes con la misma tupla
    están empatados (comparten puesto)."""
    return (
        -_score(c),
        -(c.goals_for - c.goals_against),
        -c.goals_for,
        -c.won_regular,
        -c.won_penalties,
        c.lost,  # ascendente: el que perdió menos va más arriba
    )


class RankingService:
    """Ranking global de clubes."""

    def __init__(self, repo: AbstractRankingRepository) -> None:
        self.repo = repo

    def get_global_ranking(self, page: int, name: str | None) -> GlobalRankingPage:
        """Ranking de los clubes con partidos finalizados en ligas públicas.

        `position` se calcula sobre el ranking completo, antes de filtrar por
        `name` y paginar. Los empatados en todo comparten puesto (1, 2, 2, 4) y
        se ordenan por id de club para que la paginación sea estable.
        """
        ordered = sorted(self.repo.list_club_totals(), key=lambda c: (*_criteria(c), c.club_id))

        entries: list[GlobalRankingEntry] = []
        position = 0
        previous: tuple | None = None
        for index, club in enumerate(ordered, start=1):
            criteria = _criteria(club)
            if criteria != previous:
                position = index
                previous = criteria
            entries.append(
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
            )

        if name:  # "" se trata como ausente
            needle = name.lower()
            entries = [e for e in entries if needle in e.name.lower()]

        offset = (page - 1) * PAGE_SIZE
        return GlobalRankingPage(
            items=entries[offset : offset + PAGE_SIZE],
            page=page,
            page_size=PAGE_SIZE,
            total=len(entries),
        )