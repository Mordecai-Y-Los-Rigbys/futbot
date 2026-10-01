from app.repositories.league_abstract import AbstractLeagueRepository
from app.schemas.league import LeagueCreator, LeaguePage, LeagueSummary

PAGE_SIZE = 50


class LeagueService:
    def __init__(self, repo: AbstractLeagueRepository):
        self.repo = repo

    def list_leagues(self, name: str | None, page: int) -> LeaguePage:
        data = self.repo.list_page(
            name=name or None,  # "" se trata como ausente
            offset=(page - 1) * PAGE_SIZE,
            limit=PAGE_SIZE,
        )
        items = [
            LeagueSummary(
                id=item.id,
                name=item.name,
                creator=LeagueCreator(
                    id=item.creator.id,
                    username=item.creator.username,
                    name=item.creator.club_name,  # el spec lo expone como `name`
                ),
                status=item.status,
                participants_count=item.participants_count,
                max_participants=item.max_participants,
                private=item.private,
                created_at=item.created_at,
            )
            for item in data.items
        ]
        return LeaguePage(
            items=items, page=page, page_size=PAGE_SIZE, total=data.total
        )