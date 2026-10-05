from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.api.deps import get_friendly_service
from app.api.ws_deps import get_friendly_expiry
from app.errors import ApiError
from app.main import app
from app.repositories.friendly_abstract import (
    AbstractFriendlyRepository,
    FriendlyClubData,
    FriendlyJoinState,
    FriendlyMatchData,
)
from app.schemas.errors import Error, JoinFriendlyMatchBadRequest, JoinFriendlyMatchConflict
from app.services.friendly_service import FriendlyService
from app.services.friendly_validation import JoinFriendlyInput, parse_join_friendly
from app.services.league_validation import INVALID_JSON, MemberInput
from app.tests.unit.repo_fakes import FakeBehaviors, FakePlayers


ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]
NOW = datetime(2026, 10, 4, 13, 0, tzinfo=timezone.utc)
URL = "/friendlies/100/members"

class SpyPlayers(FakePlayers):
    def __init__(self):
        super().__init__()
        self.calls = []

    def owned_player_ids(self, user_id, ids):
        self.calls.append((user_id, ids))
        return super().owned_player_ids(user_id, ids)


class SpyBehaviors(FakeBehaviors):
    def __init__(self):
        super().__init__()
        self.calls = []

    def owned_behavior_ids(self, user_id, ids):
        self.calls.append((user_id, ids))
        return super().owned_behavior_ids(user_id, ids)


# --- helpers ----------------------------------------------------------------------------

def members():
    # behaviorId alterna 21/22: el mismo behavior se reutiliza en varios jugadores
    return [
        {"playerId": 11 + i, "role": r, "behaviorId": 21 + (i % 2)}
        for i, r in enumerate(ROLES)
    ]


def body():
    return {"members": members()}


def with_member(index=0, **changes):
    b = body()
    b["members"][index].update(changes)
    return b


def without_key(key):
    b = body()
    del b["members"][0][key]
    return b


def club(id, username, name):
    return FriendlyClubData(id=id, username=username, club_name=name)


def joined_match():
    return FriendlyMatchData(
        id=100,
        name="Partido amistoso 1",
        status="scheduled",
        club1=club(1, "usuario1", "Club Atletico"),
        club2=club(2, "usuario2", "Club Visitante"),
        created_at=NOW,
    )


def state(**fields):
    base = dict(id=100, creator_id=1, rival_id=None, status="scheduled")
    base.update(fields)
    return FriendlyJoinState(**base)


# --- validación (parse_join_friendly) -------------------------------------------------------

def code_of(raw):
    with pytest.raises(ApiError) as exc:
        parse_join_friendly(raw)
    assert exc.value.status_code == 400
    return exc.value.code


INVALID_TYPE = [
    {"members": "x"}, {"members": 5}, {"members": {}}, {"members": None},
    {"members": [5, 5, 5, 5, 5, 5]},
    with_member(playerId="abc"), with_member(playerId=1.5), with_member(playerId=True),
    with_member(playerId=None), with_member(playerId=0), with_member(playerId=-1),
    with_member(playerId=2147483648),
    with_member(behaviorId="abc"), with_member(behaviorId=1.5), with_member(behaviorId=0),
    with_member(behaviorId=-1), with_member(behaviorId=2147483648),
    with_member(role=5), with_member(role=None), with_member(role=["forward"]),
]

INCOMPLETE = [
    {}, {"name": "x"},
    without_key("playerId"), without_key("role"), without_key("behaviorId"),
]

INVALID_TEAM = [
    {"members": members()[:5]},
    {"members": members() + [{"playerId": 99, "role": "substitute", "behaviorId": 21}]},
    {"members": []},
    with_member(index=1, playerId=11),         # playerId repetido
    with_member(index=1, role="forward"),      # dos forwards, ningún midfield
    with_member(index=2, role="substitute"),   # cuatro suplentes, ningún defense
    with_member(role="goalkeeper"),            # string de rol desconocido
    with_member(role=""),
    with_member(role="FORWARD"),
]


def test_valid_body_is_parsed():
    out = parse_join_friendly(body())
    assert isinstance(out, JoinFriendlyInput)
    assert out.members[0] == MemberInput(11, 21, "forward")
    assert [m.role for m in out.members] == ROLES


def test_reusing_the_same_behavior_is_not_rejected():
    b = body()
    for m in b["members"]:
        m["behaviorId"] = 21
    assert len(parse_join_friendly(b).members) == 6


def test_name_is_ignored():
    b = body()
    b["name"] = 5
    assert len(parse_join_friendly(b).members) == 6


@pytest.mark.parametrize("raw", [None, INVALID_JSON, [], [1], "x", 5, True])
def test_unreadable_body_is_incomplete_form(raw):
    assert code_of(raw) == "incompleteForm"


@pytest.mark.parametrize("raw", INVALID_TYPE)
def test_invalid_field_type(raw):
    assert code_of(raw) == "invalidFieldType"


@pytest.mark.parametrize("raw", INCOMPLETE)
def test_incomplete_form(raw):
    assert code_of(raw) == "incompleteForm"


@pytest.mark.parametrize("raw", INVALID_TEAM)
def test_invalid_team(raw):
    assert code_of(raw) == "invalidTeam"


def test_type_error_beats_incomplete_form():
    b = body()
    b["members"][0]["playerId"] = "abc"
    del b["members"][1]["role"]
    assert code_of(b) == "invalidFieldType"


def test_incomplete_form_beats_invalid_team():
    b = {"members": members()[:5]}
    del b["members"][0]["behaviorId"]
    assert code_of(b) == "incompleteForm"


def test_type_error_beats_invalid_team():
    b = {"members": members()[:5]}
    b["members"][0]["playerId"] = "abc"
    assert code_of(b) == "invalidFieldType"


# --- servicio --------------------------------------------------------------------------------

_BODY = object()

@pytest.fixture()
def players():
    return FakePlayers()


@pytest.fixture()
def behaviors():
    return FakeBehaviors()


@pytest.fixture()
def repo():
    r = MagicMock(spec=AbstractFriendlyRepository)
    r.get_friendly_state.return_value = state()
    r.user_is_playing.return_value = False
    r.join_friendly.return_value = joined_match()
    return r

def join(repo, players=None, behaviors=None, user_id=2, raw_id="100", raw_body=_BODY):
    service = FriendlyService(repo, players or FakePlayers(), behaviors or FakeBehaviors())
    return service.join_friendly(user_id, raw_id, body() if raw_body is _BODY else raw_body)


def error_of(repo, **kwargs):
    with pytest.raises(ApiError) as exc:
        join(repo, **kwargs)
    return exc.value


def test_service_success_returns_the_match_schema(repo):
    out = join(repo)
    dumped = out.model_dump(by_alias=True)
    assert dumped["id"] == 100
    assert dumped["name"] == "Partido amistoso 1"
    assert dumped["status"] == "scheduled"
    assert dumped["club1"] == {"id": 1, "username": "usuario1", "name": "Club Atletico"}
    assert dumped["club2"] == {"id": 2, "username": "usuario2", "name": "Club Visitante"}
    for k in ("leagueId", "scheduledAt", "result"):
        assert dumped[k] is None
    assert "2026-10-04T13:00:00Z" in out.model_dump_json(by_alias=True)


def test_service_persists_the_rival_team(repo):
    join(repo)
    data = repo.join_friendly.call_args.args[0]
    assert (data.match_id, data.user_id) == (100, 2)
    assert [(m.player_id, m.behavior_id, m.role) for m in data.members] == [
        (11 + i, 21 + (i % 2), r) for i, r in enumerate(ROLES)
    ]


def test_service_checks_ownership_for_the_joining_user(repo):
    players, behaviors = SpyPlayers(), SpyBehaviors()
    join(repo, players, behaviors, user_id=2)
    assert players.calls == [(2, [11, 12, 13, 14, 15, 16])]
    assert len(behaviors.calls) == 1 and behaviors.calls[0][0] == 2
    assert sorted(behaviors.calls[0][1]) == [21, 22]  # sin duplicar
    repo.user_is_playing.assert_called_once_with(2)


@pytest.mark.parametrize(
    "raw_id",
    ["abc", "1.5", "0", "-1", "2147483648", "99999999999999999999", "", "1_0", " 1", "+1", "\uff11"],
)
def test_invalid_route_id_is_404_without_touching_the_repo(repo, raw_id):
    err = error_of(repo, raw_id=raw_id)
    assert (err.status_code, err.code) == (404, None)
    assert err.message == "Partido amistoso no encontrado."
    repo.get_friendly_state.assert_not_called()


@pytest.mark.parametrize("raw_id, parsed", [("1", 1), ("2147483647", 2147483647), ("007", 7)])
def test_boundary_route_ids_are_looked_up(repo, raw_id, parsed):
    join(repo, raw_id=raw_id)
    repo.get_friendly_state.assert_called_once_with(parsed)


def test_nonexistent_match_is_404(repo):
    repo.get_friendly_state.return_value = None
    err = error_of(repo)
    assert (err.status_code, err.code) == (404, None)
    repo.join_friendly.assert_not_called()


def test_404_beats_400_for_nonexistent_match(repo):
    repo.get_friendly_state.return_value = None
    assert error_of(repo, raw_body={}).status_code == 404


def test_404_beats_400_for_invalid_route_id(repo):
    assert error_of(repo, raw_id="abc", raw_body={}).status_code == 404


def test_400_beats_409(repo):
    repo.get_friendly_state.return_value = state(rival_id=3)  # notJoinable
    err = error_of(repo, raw_body={})
    assert (err.status_code, err.code) == (400, "incompleteForm")
    repo.user_is_playing.assert_not_called()


@pytest.mark.parametrize(
    "raw_body, code",
    [
        ({"members": "x"}, "invalidFieldType"),
        ({}, "incompleteForm"),
        (None, "incompleteForm"),
        ({"members": []}, "invalidTeam"),
    ],
)
def test_400_codes_reach_the_caller_without_side_effects(repo, raw_body, code):
    err = error_of(repo, raw_body=raw_body)
    assert (err.status_code, err.code) == (400, code)
    repo.user_is_playing.assert_not_called()
    repo.join_friendly.assert_not_called()


@pytest.mark.parametrize(
    "st",
    [
        state(rival_id=3),                        # ya tiene rival (cuenta regresiva)
        state(status="started", rival_id=3),
        state(status="finished", rival_id=3),
        state(status="cancelled"),
    ],
)
def test_not_joinable(repo, st):
    repo.get_friendly_state.return_value = st
    err = error_of(repo)
    assert (err.status_code, err.code) == (409, "notJoinable")
    repo.user_is_playing.assert_not_called()
    repo.join_friendly.assert_not_called()


def test_own_match(repo):
    err = error_of(repo, user_id=1)
    assert (err.status_code, err.code) == (409, "isOwnMatch")
    repo.user_is_playing.assert_not_called()
    repo.join_friendly.assert_not_called()


def test_already_playing(repo):
    repo.user_is_playing.return_value = True
    err = error_of(repo)
    assert (err.status_code, err.code) == (409, "alreadyPlaying")
    repo.join_friendly.assert_not_called()


def test_player_not_owned_or_missing(repo):
    err = error_of(repo, players=FakePlayers(owned={11, 12, 14, 15, 16}))
    assert (err.status_code, err.code) == (409, "playerOrBehaviorNotOwned")
    repo.join_friendly.assert_not_called()


def test_behavior_not_owned_or_missing(repo):
    err = error_of(repo, behaviors=FakeBehaviors(owned={21}))
    assert err.code == "playerOrBehaviorNotOwned"
    repo.join_friendly.assert_not_called()


def test_not_joinable_beats_own_match(repo):
    repo.get_friendly_state.return_value = state(rival_id=3)
    assert error_of(repo, user_id=1).code == "notJoinable"


def test_own_match_beats_already_playing(repo):
    repo.user_is_playing.return_value = True
    assert error_of(repo, user_id=1).code == "isOwnMatch"


def test_already_playing_beats_not_owned(repo):
    repo.user_is_playing.return_value = True
    assert error_of(repo, players=FakePlayers(owned=set())).code == "alreadyPlaying"


def test_losing_the_race_in_the_database_is_not_joinable(repo):
    repo.join_friendly.return_value = None  # otro llegó antes, o venció la espera
    err = error_of(repo)
    assert (err.status_code, err.code) == (409, "notJoinable")


# --- endpoint ---------------------------------------------------------------------------------------------

class FakeExpiry:
    def __init__(self):
        self.unscheduled = []

    def unschedule(self, match_id):
        self.unscheduled.append(match_id)


@pytest.fixture()
def expiry():
    return FakeExpiry()


@pytest.fixture()
def join_api(api, repo, players, behaviors, expiry):
    app.dependency_overrides[get_friendly_service] = lambda: FriendlyService(repo, players, behaviors)
    app.dependency_overrides[get_friendly_expiry] = lambda: expiry
    return api


@pytest.fixture()
def auth_join_api(join_api):
    join_api.cookies.set("session_id", "valid-session")  # usuario 7
    return join_api


def nothing_scheduled(expiry):
    return expiry.unscheduled == []


def test_endpoint_success_full_structure(auth_join_api, repo, expiry):
    resp = auth_join_api.post(URL, json=body())
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "id": 100,
        "leagueId": None,
        "name": "Partido amistoso 1",
        "status": "scheduled",
        "club1": {"id": 1, "username": "usuario1", "name": "Club Atletico"},
        "club2": {"id": 2, "username": "usuario2", "name": "Club Visitante"},
        "scheduledAt": None,
        "createdAt": "2026-10-04T13:00:00Z",
        "result": None,
    }
    assert repo.join_friendly.call_args.args[0].user_id == 7  # el usuario de la sesión
    assert expiry.unscheduled == [100]  # se cancela el vencimiento de 15 min


@pytest.mark.parametrize(
    "path, payload",
    [
        (URL, body()),
        ("/friendlies/abc/members", {"members": 5}),
        ("/friendlies/0/members", {}),
        ("/friendlies/2147483648/members", {"members": []}),
    ],
)
def test_no_cookie_is_401_even_with_bad_id_or_body(join_api, repo, expiry, path, payload):
    resp = join_api.post(path, json=payload)
    assert resp.status_code == 401
    assert resp.json()["code"] is None
    Error.model_validate(resp.json())
    repo.get_friendly_state.assert_not_called()
    assert nothing_scheduled(expiry)


@pytest.mark.parametrize("cookie", ["no-existe", "vencida"])
def test_invalid_or_expired_cookie_is_401(join_api, repo, expiry, cookie):
    join_api.cookies.set("session_id", cookie)
    resp = join_api.post("/friendlies/abc/members", json={"members": 5})
    assert resp.status_code == 401 and resp.json()["code"] is None
    repo.get_friendly_state.assert_not_called()
    assert nothing_scheduled(expiry)


@pytest.mark.parametrize("raw_id", ["abc", "1.5", "0", "-1", "2147483648", "99999999999999999999"])
def test_invalid_route_id_is_404_never_422(auth_join_api, repo, expiry, raw_id):
    resp = auth_join_api.post(f"/friendlies/{raw_id}/members", json=body())
    assert resp.status_code == 404
    assert resp.json()["code"] is None
    Error.model_validate(resp.json())
    repo.get_friendly_state.assert_not_called()
    assert nothing_scheduled(expiry)


def test_invalid_route_id_beats_invalid_body(auth_join_api):
    assert auth_join_api.post("/friendlies/abc/members", json={"members": 5}).status_code == 404
    assert auth_join_api.post("/friendlies/abc/members").status_code == 404


def test_nonexistent_match_is_404(auth_join_api, repo, expiry):
    repo.get_friendly_state.return_value = None
    resp = auth_join_api.post(URL, json=body())
    assert resp.status_code == 404
    assert resp.json() == {"code": None, "message": "Partido amistoso no encontrado."}
    assert nothing_scheduled(expiry)


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({}, "incompleteForm"),  # sin body
        ({"content": "{", "headers": {"Content-Type": "application/json"}}, "incompleteForm"),
        ({"json": []}, "incompleteForm"),
        ({"json": "x"}, "incompleteForm"),
        ({"json": 5}, "incompleteForm"),
        ({"json": {}}, "incompleteForm"),
        ({"json": {"members": "x"}}, "invalidFieldType"),
        (
            {"json": {"members": [{"playerId": "abc", "role": "forward", "behaviorId": 1}]}},
            "invalidFieldType",
        ),
        ({"json": {"members": []}}, "invalidTeam"),
    ],
)
def test_body_errors_are_400_never_422(auth_join_api, repo, expiry, kwargs, code):
    resp = auth_join_api.post(URL, **kwargs)
    assert resp.status_code == 400
    assert resp.json()["code"] == code
    assert resp.json()["message"]
    JoinFriendlyMatchBadRequest.model_validate(resp.json())
    repo.join_friendly.assert_not_called()
    assert nothing_scheduled(expiry)


@pytest.mark.parametrize(
    "setup, code",
    [
        (lambda r, p, b: setattr(r.get_friendly_state, "return_value", state(rival_id=3)), "notJoinable"),
        (lambda r, p, b: setattr(r.get_friendly_state, "return_value", state(creator_id=7)), "isOwnMatch"),
        (lambda r, p, b: setattr(r.user_is_playing, "return_value", True), "alreadyPlaying"),
        (lambda r, p, b: setattr(p, "owned", set()), "playerOrBehaviorNotOwned"),
        (lambda r, p, b: setattr(b, "owned", set()), "playerOrBehaviorNotOwned"),
        (lambda r, p, b: setattr(r.join_friendly, "return_value", None), "notJoinable"),
    ],
)
def test_conflicts_are_409_and_schedule_nothing(auth_join_api, repo, players, behaviors, expiry, setup, code):
    setup(repo, players, behaviors)
    resp = auth_join_api.post(URL, json=body())
    assert resp.status_code == 409
    assert resp.json()["code"] == code
    JoinFriendlyMatchConflict.model_validate(resp.json())
    assert nothing_scheduled(expiry)