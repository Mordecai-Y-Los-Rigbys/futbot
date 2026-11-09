from datetime import datetime, timedelta, timezone

import pytest

from app.domain.behavior import BehaviorType
from app.domain.team_member import MemberRole
from app.errors import ApiError
from app.repositories.behavior_abstract import BehaviorData
from app.repositories.behavior_test_token_abstract import BehaviorTestMemberData
from app.services import behavior_test_connection_service as module
from app.services.behavior_test_connection_service import BehaviorTestConnectionService
from app.tests.unit.repo_fakes import FakePlayers

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
USER, OTHER = 7, 8
ROUTE, SECOND, COACH = 4, 5, 6
LINEUP = [
    ("club1", "forward"),
    ("club1", "midfield"),
    ("club1", "defense"),
    ("club2", "forward"),
    ("club2", "midfield"),
    ("club2", "defense"),
]


class FakeTokens:
    def __init__(self):
        self.created = []

    def create(self, data):
        self.created.append(data)

    def get_by_token(self, token):
        return None


class FakeBehaviors:
    def __init__(self, *records):
        self.records = {r.id: r for r in records}

    def get_by_id(self, behavior_id):
        return self.records.get(behavior_id)

    def behavior_types(self, user_id, ids):
        return {
            i: self.records[i].type
            for i in ids
            if i in self.records and self.records[i].user_id == user_id
        }


def behavior(id=ROUTE, user_id=USER, type=BehaviorType.player_behavior):
    return BehaviorData(id=id, user_id=user_id, name="b", code="pass", type=type)


def body(behavior_id=ROUTE):
    return {
        "members": [
            {"playerId": i + 1, "club": club, "role": role, "behaviorId": behavior_id}
            for i, (club, role) in enumerate(LINEUP)
        ]
    }


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(module, "_utcnow", lambda: NOW)


@pytest.fixture()
def tokens():
    return FakeTokens()


def make_service(tokens, *records, players=None):
    return BehaviorTestConnectionService(FakeBehaviors(*records), players or FakePlayers(), tokens)


def error_of(service, payload):
    with pytest.raises(ApiError) as exc:
        service.connect(USER, ROUTE, payload)
    return exc.value.status_code, exc.value.code


# --- 201 ----------------------------------------------------------------------


def test_creates_a_token_tied_to_the_user_the_behavior_and_the_lineup(tokens):
    token = make_service(tokens, behavior()).connect(USER, ROUTE, body())

    [saved] = tokens.created
    assert saved.token == token
    assert (saved.user_id, saved.behavior_id) == (USER, ROUTE)
    assert saved.created_at == NOW
    assert saved.expires_at == NOW + timedelta(minutes=5)
    assert saved.members == [
        BehaviorTestMemberData(
            player_id=i + 1, club=club, role=MemberRole(role), behavior_id=ROUTE
        )
        for i, (club, role) in enumerate(LINEUP)
    ]


def test_each_call_creates_a_new_token(tokens):
    service = make_service(tokens, behavior())
    assert service.connect(USER, ROUTE, body()) != service.connect(USER, ROUTE, body())


def test_the_route_behavior_does_not_have_to_be_in_the_lineup(tokens):
    make_service(tokens, behavior(), behavior(SECOND)).connect(USER, ROUTE, body(SECOND))
    assert {m.behavior_id for m in tokens.created[0].members} == {SECOND}


# --- errores ------------------------------------------------------------------


def test_unknown_behavior_is_404(tokens):
    assert error_of(make_service(tokens), body()) == (404, None)
    assert tokens.created == []


def test_invalid_body_is_400(tokens):
    assert error_of(make_service(tokens, behavior()), {"members": []}) == (400, "invalidFields")
    assert tokens.created == []


def test_behavior_of_another_user_is_403(tokens):
    assert error_of(make_service(tokens, behavior(user_id=OTHER)), body()) == (403, None)
    assert tokens.created == []


def test_coach_behavior_is_409_not_player_behavior(tokens):
    coach = behavior(type=BehaviorType.coach_behavior)
    assert error_of(make_service(tokens, coach), body()) == (409, "notPlayerBehavior")
    assert tokens.created == []


@pytest.mark.parametrize(
    "players, member_behavior",
    [(FakePlayers(owned={1, 2, 3, 4, 5}), ROUTE), (None, SECOND), (None, 99)],
    ids=["jugador ajeno", "behavior ajeno", "behavior inexistente"],
)
def test_lineup_not_owned_is_409(tokens, players, member_behavior):
    service = make_service(tokens, behavior(), behavior(SECOND, OTHER), players=players)
    assert error_of(service, body(member_behavior)) == (409, "playerOrBehaviorNotOwned")
    assert tokens.created == []


def test_coach_behavior_in_the_lineup_is_409_type_mismatch(tokens):
    service = make_service(tokens, behavior(), behavior(COACH, type=BehaviorType.coach_behavior))
    assert error_of(service, body(COACH)) == (409, "behaviorTypeMismatch")
    assert tokens.created == []


# --- precedencia: 404 > 400 > 403 > 409 ---------------------------------------


def test_404_beats_400(tokens):
    assert error_of(make_service(tokens), None) == (404, None)


def test_400_beats_403(tokens):
    assert error_of(make_service(tokens, behavior(user_id=OTHER)), None)[0] == 400


def test_403_beats_409(tokens):
    foreign_coach = behavior(user_id=OTHER, type=BehaviorType.coach_behavior)
    assert error_of(make_service(tokens, foreign_coach), body()) == (403, None)


def test_not_player_behavior_comes_before_the_other_409(tokens):
    coach = behavior(type=BehaviorType.coach_behavior)
    service = make_service(tokens, coach, players=FakePlayers(owned=set()))
    assert error_of(service, body()) == (409, "notPlayerBehavior")


def test_not_owned_comes_before_type_mismatch(tokens):
    service = make_service(
        tokens,
        behavior(),
        behavior(COACH, type=BehaviorType.coach_behavior),
        players=FakePlayers(owned=set()),
    )
    assert error_of(service, body(COACH)) == (409, "playerOrBehaviorNotOwned")
