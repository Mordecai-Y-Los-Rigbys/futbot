from app.repositories.player_abstract import AbstractPlayerRepository, PlayerData
from app.services.player_service import PlayerService


class FakePlayerRepository(AbstractPlayerRepository):
    def __init__(self, players: list[PlayerData] | None = None):
        self.players = players or []

    def list_by_user_id(self, user_id: int) -> list[PlayerData]:
        return [p for p in self.players if p.user_id == user_id]


def test_get_my_players_returns_user_players():
    p1 = PlayerData(id=1, user_id=10, name="Messi", power=60, agility=60, control=60, strength=60, speed=60)
    p2 = PlayerData(id=2, user_id=10, name="Di Maria", power=60, agility=60, control=60, strength=60, speed=60)
    p3 = PlayerData(id=3, user_id=99, name="Ronaldo", power=60, agility=60, control=60, strength=60, speed=60)

    service = PlayerService(FakePlayerRepository([p1, p2, p3]))
    res = service.get_my_players(user_id=10)

    assert len(res) == 2
    assert [p.name for p in res] == ["Messi", "Di Maria"]


def test_get_my_players_returns_empty_list_when_no_players():
    service = PlayerService(FakePlayerRepository([]))
    res = service.get_my_players(user_id=10)
    assert res == []