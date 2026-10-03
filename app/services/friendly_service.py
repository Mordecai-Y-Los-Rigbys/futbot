from typing import Any

from app.errors import ApiError
from app.repositories.friendly_abstract import (
    AbstractFriendlyRepository,
    CreateFriendlyData,
    CreateFriendlyMemberData,
    FriendlyMatchData,
)
from app.schemas.friendly import MatchClub, MatchPage, MatchResponse
from app.services.friendly_validation import parse_create_friendly

PAGE_SIZE = 50
       
       
def _to_response(m: FriendlyMatchData) -> MatchResponse:
    return MatchResponse(
        id=m.id,
        league_id=None,
        name=m.name,
        status=m.status,
        club1=MatchClub(id=m.club1.id, username=m.club1.username, name=m.club1.club_name),
        club2=None,
        scheduled_at=None,
        created_at=m.created_at,
        result=None,
    )


class FriendlyService:
    def __init__(self, repo: AbstractFriendlyRepository):
        self.repo = repo

    def create_friendly(self, creator_id: int, body: Any) -> MatchResponse:
        data = parse_create_friendly(body)  # todos los 400, en orden

        # 409: solo si no falló ningún 400
        if self.repo.user_is_playing(creator_id):
            raise ApiError(409, "alreadyPlaying", "Ya estás jugando otro partido.")

        player_ids = [m.player_id for m in data.members]
        behavior_ids = list({m.behavior_id for m in data.members})
        if (
            self.repo.owned_player_ids(creator_id, player_ids) != set(player_ids)
            or self.repo.owned_behavior_ids(creator_id, behavior_ids) != set(behavior_ids)
        ):
            raise ApiError(
                409,
                "playerOrBehaviorNotOwned",
                "Uno o más jugadores o comportamientos no te pertenecen.",
            )

        created = self.repo.create_with_team(
            CreateFriendlyData(
                name=data.name,
                creator_id=creator_id,
                members=[
                    CreateFriendlyMemberData(
                        player_id=m.player_id, behavior_id=m.behavior_id, role=m.role
                    )
                    for m in data.members
                ],
            )
        )
        return _to_response(created)

    def list_waiting_friendlies(self, user_id: int, name: str | None, page: int) -> MatchPage:
        data = self.repo.list_waiting_page(
            exclude_user_id=user_id,
            name=name or None,  # "" se trata como ausente
            offset=(page - 1) * PAGE_SIZE,
            limit=PAGE_SIZE,
        )
        return MatchPage(
            items=[_to_response(i) for i in data.items],
            page=page,
            page_size=PAGE_SIZE,
            total=data.total,
        )
