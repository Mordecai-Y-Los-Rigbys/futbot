from typing import Any
from app.repositories.player_abstract import AbstractPlayerRepository
from app.schemas.player import PlayerResponse, PlayerStats
from app.services.player_validation import parse_create_player

PAGE_SIZE = 50

class PlayerService:
    def __init__(self, repository: AbstractPlayerRepository):
        self.repository = repository

    def create_player(self, user_id: int, body: Any) -> PlayerResponse:
        data = parse_create_player(body)
        
        player_data = self.repository.create(user_id=user_id, data=data)
        
        stats = PlayerStats(
            power=player_data.power,
            agility=player_data.agility,
            control=player_data.control,
            strength=player_data.strength,
            speed=player_data.speed
        )
        
        return PlayerResponse(
            id=player_data.id,
            name=player_data.name,
            stats=stats,
            deletable=player_data.deletable
        )
    
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
                deletable=p.deletable  
            ))
            
        return items, total
        