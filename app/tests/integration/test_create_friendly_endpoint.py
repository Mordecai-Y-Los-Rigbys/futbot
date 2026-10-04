import pytest

from app.api.ws_deps import get_friendly_expiry
from app.domain.match import MatchStatus
from app.main import app
from app.models.match import Match
from app.models.team_member import TeamMember
from app.models.player import Player

pytestmark = pytest.mark.integration

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


class FakeExpiry:
    def __init__(self):
        self.calls = []

    def schedule(self, match_id, created_at=None):
        self.calls.append((match_id, created_at))


@pytest.fixture()
def expiry():
    fake = FakeExpiry()
    app.dependency_overrides[get_friendly_expiry] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_friendly_expiry, None)


@pytest.fixture()
def setup(db_session, make_user, make_behaviors):
    user = make_user(1)
    players = [
        Player(user_id=user.id, name=f"J{i}", power=60, agility=60,
               control=60, strength=60, speed=60)
        for i in range(6)
    ]
    db_session.add_all(players)
    db_session.commit()
    behaviors = make_behaviors(user.id, [f"b{i}" for i in range(6)])
    return user, players, behaviors


def payload(players, behaviors, name="Partido amistoso 1"):
    return {
        "name": name,
        "members": [
            {"playerId": p.id, "role": r, "behaviorId": b.id}
            for p, r, b in zip(players, ROLES, behaviors)
        ],
    }


def test_without_session_is_401_even_with_bad_body(client, expiry):
    r = client.post("/friendlies", json={"name": 5})
    assert r.status_code == 401 and r.json()["code"] is None
    assert expiry.calls == []


def test_success_creates_match_and_team(client, login, db_session, setup, expiry):
    user, players, behaviors = setup
    login(user.id)
    r = client.post("/friendlies", json=payload(players, behaviors))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "scheduled"
    assert body["leagueId"] is None and body["club2"] is None
    assert body["scheduledAt"] is None and body["result"] is None
    assert body["club1"]["id"] == user.id
    assert body["createdAt"].endswith("Z")

    match = db_session.get(Match, body["id"])
    assert match.status == MatchStatus.scheduled and match.user_2_id is None
    assert db_session.query(TeamMember).filter_by(match_id=match.id).count() == 6
    assert expiry.calls == [(body["id"], expiry.calls[0][1])]


def test_invalid_body_is_400_and_creates_nothing(client, login, db_session, setup, expiry):
    user, players, behaviors = setup
    login(user.id)
    r = client.post("/friendlies", json=payload(players, behaviors, name="x" * 21))
    assert r.status_code == 400 and r.json()["code"] == "nameTooLong"
    assert db_session.query(Match).count() == 0
    assert expiry.calls == []


def test_second_friendly_while_waiting_is_already_playing(client, login, setup, expiry):
    user, players, behaviors = setup
    login(user.id)
    assert client.post("/friendlies", json=payload(players, behaviors)).status_code == 201
    r = client.post("/friendlies", json=payload(players, behaviors))
    assert r.status_code == 409 and r.json()["code"] == "alreadyPlaying"
    assert len(expiry.calls) == 1


def test_foreign_player_is_409_not_owned(client, login, db_session, make_user, setup, expiry):
    user, players, behaviors = setup
    other = make_user(2)
    stranger = Player(user_id=other.id, name="Ajeno", power=60, agility=60,
                      control=60, strength=60, speed=60)
    db_session.add(stranger)
    db_session.commit()
    players[0] = stranger
    login(user.id)
    r = client.post("/friendlies", json=payload(players, behaviors))
    assert r.status_code == 409 and r.json()["code"] == "playerOrBehaviorNotOwned"
    assert db_session.query(Match).count() == 0


def test_foreign_behavior_is_409_not_owned(client, login, db_session, make_user, make_behaviors, setup, expiry):
    user, players, behaviors = setup
    other = make_user(2)
    foreign = make_behaviors(other.id, ["ajeno"])[0]
    behaviors[0] = foreign
    login(user.id)
    r = client.post("/friendlies", json=payload(players, behaviors))
    assert r.status_code == 409 and r.json()["code"] == "playerOrBehaviorNotOwned"
    assert db_session.query(Match).count() == 0


def test_nonexistent_ids_are_409_not_owned(client, login, setup, expiry):
    user, players, behaviors = setup
    login(user.id)
    body = payload(players, behaviors)
    body["members"][0]["playerId"] = 2147483647
    r = client.post("/friendlies", json=body)
    assert r.status_code == 409 and r.json()["code"] == "playerOrBehaviorNotOwned"


def test_invalid_cookie_is_401(client, expiry):
    client.cookies.set("session_id", "no-existe")
    r = client.post("/friendlies", json={"name": 5})
    assert r.status_code == 401 and r.json()["code"] is None
