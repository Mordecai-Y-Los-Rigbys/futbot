from app.repositories.player_abstract import AbstractPlayerRepository
from app.schemas.player import PlayerResponse, PlayerStats

PAGE_SIZE = 50

class PlayerService:
    def __init__(self, repository: AbstractPlayerRepository):
        self.repository = repository

    def get_user_players(
        self, user_id: int, name: str | None, page: int
    ) -> tuple[list[PlayerResponse], int]:
        offset = (page - 1) * PAGE_SIZE
        
        players_data, total = self.repository.list_by_user(user_id, name, offset, PAGE_SIZE)
        
        items = []
        for p in players_data:
            stats = PlayerStats(
                power=p.power,
                agility=p.agility,
                control=p.control,
                strength=p.strength,
                speed=p.speed
            )
            items.append(PlayerResponse(
                id=p.id,
                name=p.name,
                stats=stats,
                deletable=True  
            ))
            
        return items, total
        