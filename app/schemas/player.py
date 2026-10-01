from pydantic import ConfigDict
from app.schemas.base import CamelModel

class PlayerStats(CamelModel):
    power: int
    agility: int
    control: int
    strength: int
    speed: int

    model_config = ConfigDict(from_attributes=True)
    
class PlayerResponse(CamelModel):
    id: int
    name: str
    stats: PlayerStats
    deletable: bool


class PlayerPage(CamelModel):
    items: list[PlayerResponse]
    page: int
    page_size: int 
    total: int