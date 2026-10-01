from pydantic import BaseModel, ConfigDict


class PlayerResponse(BaseModel):
    id: int
    name: str
    power: int
    agility: int
    control: int
    strength: int
    speed: int

    model_config = ConfigDict(from_attributes=True)