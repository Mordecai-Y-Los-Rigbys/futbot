from typing import Any

from app.errors import ApiError
from app.repositories.friendly_abstract import (
    AbstractFriendlyRepository,
    CreateFriendlyData,
    CreateFriendlyMemberData,
)
from app.schemas.friendly import MatchClub, MatchResponse
from app.services.friendly_validation import parse_create_friendly


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
        return MatchResponse(
            id=created.id,
            league_id=None,
            name=created.name,
            status=created.status,
            club1=MatchClub(
                id=created.club1.id,
                username=created.club1.username,
                name=created.club1.club_name,
            ),
            club2=None,
            scheduled_at=None,
            created_at=created.created_at,
            result=None,
        )
