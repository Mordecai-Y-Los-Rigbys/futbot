from app.schemas.base import CamelModel


class GlobalRankingEntry(CamelModel):
    position: int
    name: str
    avatar: int
    score: int
    goal_difference: int
    goals: int
    won_regular: int
    won_penalties: int
    lost: int


class GlobalRankingPage(CamelModel):
    items: list[GlobalRankingEntry]
    page: int
    page_size: int
    total: int
    

class LeagueRankingEntry(CamelModel):
    position: int
    name: str
    avatar: int
    played: int
    won_regular: int
    won_penalties: int
    drawn: int
    lost: int
    goals: int
    goal_difference: int
    score: int