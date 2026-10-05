from app.repositories.player_abstract import AbstractPlayerRepository, PlayerData
from app.services.player_service import PlayerService
from app.services.player_validation import CreatePlayerInput


class FakePlayerRepository(AbstractPlayerRepository):
    def __init__(self, players: list[PlayerData] | None = None):
        self.players = players or []

    def create(self, player: CreatePlayerInput, user_id: int) -> PlayerData:
        new_id = len(self.players) + 1
        new_player = PlayerData(
            id=new_id,
            user_id=user_id,
            name=player.name,
            power=player.power,
            agility=player.agility,
            control=player.control,
            strength=player.strength,
            speed=player.speed,
        )
        self.players.append(new_player)
        return new_player

    def list_by_user(
        self, user_id: int, name: str | None, offset: int, limit: int
    ) -> tuple[list[PlayerData], int]:
        filtered = [p for p in self.players if p.user_id == user_id]

        if name:
            filtered = [p for p in filtered if name.lower() in p.name.lower()]

        total = len(filtered)
        paginated = filtered[offset : offset + limit]

        return paginated, total

    def owned_player_ids(self, user_id, ids):
        return {p.id for p in self.players if p.user_id == user_id and p.id in ids}


def test_get_my_players_returns_user_players():
    p1 = PlayerData(
        id=1, user_id=10, name="Messi", power=60, agility=60, control=60, strength=60, speed=60
    )
    p2 = PlayerData(
        id=2, user_id=10, name="Di Maria", power=60, agility=60, control=60, strength=60, speed=60
    )
    p3 = PlayerData(
        id=3, user_id=99, name="Ronaldo", power=60, agility=60, control=60, strength=60, speed=60
    )

    service = PlayerService(FakePlayerRepository([p1, p2, p3]))
    items, total = service.get_user_players(user_id=10, name=None, page=1)

    assert total == 2
    assert len(items) == 2
    assert [p.name for p in items] == ["Messi", "Di Maria"]
    assert items[0].stats.power == 60


def test_get_my_players_returns_empty_list_when_no_players():
    service = PlayerService(FakePlayerRepository([]))
    items, total = service.get_user_players(user_id=10, name=None, page=1)

    assert items == []
    assert total == 0


def test_get_my_players_filters_by_name():
    p1 = PlayerData(
        id=1,
        user_id=10,
        name="Lionel Messi",
        power=60,
        agility=60,
        control=60,
        strength=60,
        speed=60,
    )
    p2 = PlayerData(
        id=2,
        user_id=10,
        name="Emiliano Martinez",
        power=60,
        agility=60,
        control=60,
        strength=60,
        speed=60,
    )

    service = PlayerService(FakePlayerRepository([p1, p2]))

    items, total = service.get_user_players(user_id=10, name="messi", page=1)

    assert total == 1
    assert items[0].name == "Lionel Messi"
