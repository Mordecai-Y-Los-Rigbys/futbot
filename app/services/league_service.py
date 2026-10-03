from typing import Any

from app.errors import ApiError
from app.repositories.league_abstract import (
    AbstractLeagueRepository,
    CreateLeagueData,
    CreateLeagueMemberData,   # <- falta en tu import; sin esto create_league falla con NameError
    LeagueListItemData,
)
from app.repositories.team_abstract import AbstractTeamRepository
from app.schemas.league import LeagueCreator, LeaguePage, LeagueSummary
from app.services.league_validation import parse_create_league

PAGE_SIZE = 50


def _to_summary(item: LeagueListItemData) -> LeagueSummary:
    return LeagueSummary(
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


class LeagueService:
    def __init__(self, repo: AbstractLeagueRepository, teams: AbstractTeamRepository):
        self.repo = repo
        self.teams = teams

    def list_leagues(self, name: str | None, page: int) -> LeaguePage:
        data = self.repo.list_page(
            name=name or None,  # "" se trata como ausente
            offset=(page - 1) * PAGE_SIZE,
            limit=PAGE_SIZE,
        )
        return LeaguePage(
            items=[_to_summary(i) for i in data.items],
            page=page,
            page_size=PAGE_SIZE,
            total=data.total,
        )

    def create_league(self, creator_id: int, body: Any) -> LeagueSummary:
        data = parse_create_league(body)  # todos los 400, en orden

        # 409: solo si no falló ningún 400
        player_ids = [m.player_id for m in data.members]
        behavior_ids = list({m.behavior_id for m in data.members})
        if (
            self.teams.owned_player_ids(creator_id, player_ids) != set(player_ids)
            or self.teams.owned_behavior_ids(creator_id, behavior_ids) != set(behavior_ids)
        ):
            raise ApiError(409, "playerOrBehaviorNotOwned", "Algún jugador o behavior no pertenece al usuario.")

        created = self.repo.create(
            CreateLeagueData(
                name=data.name,
                creator_id=creator_id,
                min_participants=data.min_participants,
                max_participants=data.max_participants,
                match_duration=data.match_duration,
                private=data.private,
                password=data.password,  # None si es pública
                members=[
                    CreateLeagueMemberData(
                        player_id=m.player_id,
                        behavior_id=m.behavior_id,
                        role=m.role,
                    )
                    for m in data.members
                ],
            )
        )
        return _to_summary(created)