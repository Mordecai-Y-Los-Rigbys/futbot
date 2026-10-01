from app.repositories.player_abstract import AbstractPlayerRepository
from app.schemas.player import PlayerResponse


class PlayerService:
    def __init__(self, repo: AbstractPlayerRepository):
        self.repo = repo

    def get_my_players(self, user_id: int) -> list[PlayerResponse]:
        players = self.repo.list_by_user_id(user_id)
        return [
            PlayerResponse(
                id=p.id,
                name=p.name,
                power=p.power,
                agility=p.agility,
                control=p.control,
                strength=p.strength,
                speed=p.speed,
            )
            for p in players
        ]