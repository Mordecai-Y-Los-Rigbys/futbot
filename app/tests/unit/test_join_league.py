"""POST /leagues/{id}/participants: validación, servicio y endpoint, sin base."""

from unittest.mock import MagicMock

import pytest

from app.api.deps import get_league_service
from app.domain.behavior import BehaviorType
from app.domain.league import LeagueStatus
from app.errors import ApiError, ValidationApiError
from app.main import app
from app.repositories.league_abstract import AbstractLeagueRepository, LeagueJoinState
from app.schemas.errors import (
    Error,
    JoinLeagueConflict,
    JoinLeagueForbidden,
    ValidationBadRequest,
)
from app.services.join_league_validation import JoinLeagueInput, parse_join_league
from app.services.league_service import LeagueService
from app.services.league_validation import INVALID_JSON, MemberInput
from app.tests.unit.repo_fakes import FakePlayers

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]
PLAYER, COACH = BehaviorType.player_behavior, BehaviorType.coach_behavior
URL = "/leagues/5/participants"
COACH_ID = 30


# --- helpers ------------------------------------------------------------------


def members():
    # behaviorId alterna 21/22: el mismo behavior se reutiliza en varios jugadores
    return [
        {"playerId": 11 + i, "role": r, "behaviorId": 21 + (i % 2)} for i, r in enumerate(ROLES)
    ]


def body(**extra):
    return {"members": members(), "coachBehaviorId": COACH_ID, **extra}


def with_member(index=0, **changes):
    b = body()
    b["members"][index].update(changes)
    return b


def without_member_key(key, index=0):
    b = body()
    del b["members"][index][key]
    return b


def errors_of(raw, private=False):
    with pytest.raises(ValidationApiError) as exc:
        parse_join_league(raw, private)
    assert (exc.value.status_code, exc.value.code) == (400, "invalidFields")
    return [(e["field"], e["reason"]) for e in exc.value.errors]


# --- validación: casos válidos ------------------------------------------------


def test_valid_body_is_parsed():
    out = parse_join_league(body(), private=False)
    assert isinstance(out, JoinLeagueInput)
    assert out.members[0] == MemberInput(11, 21, "forward")
    assert [m.role for m in out.members] == ROLES
    assert out.coach_behavior_id == COACH_ID
    assert out.password is None


@pytest.mark.parametrize("raw", [{"members": members()}, body(coachBehaviorId=None)])
def test_coach_is_optional_and_null_means_no_coach(raw):
    assert parse_join_league(raw, private=False).coach_behavior_id is None


@pytest.mark.parametrize("password", [123, None, [], {"a": 1}, True, "x" * 500])
def test_public_league_ignores_password_completely(password):
    assert parse_join_league(body(password=password), private=False).password is None


def test_private_league_keeps_the_password():
    assert parse_join_league(body(password="secret"), private=True).password == "secret"


def test_empty_password_is_not_a_validation_error():
    # "" no es 400: lo resuelve el 403 invalidLeaguePassword
    assert parse_join_league(body(password=""), private=True).password == ""


def test_unknown_fields_are_ignored():
    assert len(parse_join_league(body(name=5, extra=[1]), private=False).members) == 6


def test_reusing_the_same_behavior_is_valid():
    b = body()
    for m in b["members"]:
        m["behaviorId"] = 21
    assert len(parse_join_league(b, private=False).members) == 6


# --- validación: body ilegible (convención 9) ---------------------------------


@pytest.mark.parametrize("raw", [None, INVALID_JSON, [], [1], "x", 5, True, {}])
def test_unreadable_body_public(raw):
    assert errors_of(raw, private=False) == [("members", "required")]


@pytest.mark.parametrize("raw", [None, INVALID_JSON, [], [1], "x", 5, True, {}])
def test_unreadable_body_private_puts_password_first(raw):
    assert errors_of(raw, private=True) == [("password", "required"), ("members", "required")]


# --- validación: password -----------------------------------------------------


@pytest.mark.parametrize("raw", [body(), body(password=None)])
def test_private_password_missing_or_null_is_required(raw):
    assert errors_of(raw, private=True) == [("password", "required")]


@pytest.mark.parametrize("password", [123, 1.5, True, [], {}])
def test_private_password_not_a_string_is_invalid_type(password):
    assert errors_of(body(password=password), private=True) == [("password", "invalidType")]


# --- validación: members ------------------------------------------------------


def test_members_missing_is_required():
    assert errors_of({"coachBehaviorId": COACH_ID}) == [("members", "required")]


@pytest.mark.parametrize("value", ["x", 5, {}, None, True])
def test_members_not_an_array_is_invalid_type(value):
    assert errors_of({"members": value}) == [("members", "invalidType")]


@pytest.mark.parametrize("element", [5, "x", None, [], True])
def test_member_that_is_not_an_object_is_invalid_type(element):
    b = body()
    b["members"][2] = element
    assert errors_of(b) == [("members[2]", "invalidType")]


@pytest.mark.parametrize("key", ["playerId", "role", "behaviorId"])
def test_member_key_missing_is_required(key):
    assert errors_of(without_member_key(key, index=3)) == [(f"members[3].{key}", "required")]


@pytest.mark.parametrize("key", ["playerId", "behaviorId"])
@pytest.mark.parametrize("value", ["abc", "1", 1.5, 1.0, True, False, None, [], {}])
def test_member_id_not_an_integer_is_invalid_type(key, value):
    assert errors_of(with_member(**{key: value})) == [(f"members[0].{key}", "invalidType")]


@pytest.mark.parametrize("key", ["playerId", "behaviorId"])
@pytest.mark.parametrize("value", [0, -1, 2147483648, 10**30])
def test_member_id_out_of_range(key, value):
    assert errors_of(with_member(**{key: value})) == [(f"members[0].{key}", "outOfRange")]


@pytest.mark.parametrize("key", ["playerId", "behaviorId"])
@pytest.mark.parametrize("value", [1, 2147483647])
def test_member_id_boundaries_are_valid(key, value):
    b = body()
    for m in b["members"]:
        if key == "behaviorId":
            m[key] = value
    if key == "playerId":
        b["members"][0][key] = value
    parse_join_league(b, private=False)


@pytest.mark.parametrize("value", [5, None, ["forward"], True])
def test_role_not_a_string_is_invalid_type(value):
    assert errors_of(with_member(role=value)) == [("members[0].role", "invalidType")]


INVALID_TEAM = [
    {"members": members()[:5]},
    {"members": members() + [{"playerId": 99, "role": "substitute", "behaviorId": 21}]},
    {"members": []},
    with_member(index=1, playerId=11),  # playerId repetido
    with_member(index=1, role="forward"),  # dos forwards, ningún midfield
    with_member(index=2, role="substitute"),  # cuatro suplentes, ningún defense
    with_member(role="goalkeeper"),  # string de rol desconocido (6.h)
    with_member(role=""),
    with_member(role="FORWARD"),
]


@pytest.mark.parametrize("raw", INVALID_TEAM)
def test_invalid_team(raw):
    assert errors_of(raw) == [("members", "invalidTeam")]


def test_invalid_team_is_not_evaluated_when_an_element_has_errors():
    b = {"members": members()[:5]}  # también tiene 5 elementos
    b["members"][0]["playerId"] = "abc"
    assert errors_of(b) == [("members[0].playerId", "invalidType")]


def test_one_reason_per_field():
    # playerId falta: solo required, aunque tampoco haya rango que validar
    b = without_member_key("playerId")
    b["members"][0]["role"] = 5
    assert errors_of(b) == [("members[0].playerId", "required"), ("members[0].role", "invalidType")]


# --- validación: coachBehaviorId ----------------------------------------------


@pytest.mark.parametrize("value", ["abc", "17", 1.5, 1.0, True, [], {}])
def test_coach_not_an_integer_is_invalid_type(value):
    assert errors_of(body(coachBehaviorId=value)) == [("coachBehaviorId", "invalidType")]


@pytest.mark.parametrize("value", [0, -1, 2147483648])
def test_coach_out_of_range(value):
    assert errors_of(body(coachBehaviorId=value)) == [("coachBehaviorId", "outOfRange")]


def test_coach_does_not_take_part_in_invalid_team():
    b = {"members": members()[:5], "coachBehaviorId": "x"}
    assert errors_of(b) == [("members", "invalidTeam"), ("coachBehaviorId", "invalidType")]


# --- validación: varios errores juntos, en el orden del schema ----------------


def test_all_errors_are_reported_in_schema_order():
    b = {
        "coachBehaviorId": "x",  # el orden de las claves del body no importa
        "members": members(),
        "password": 5,
    }
    b["members"][0]["playerId"] = "abc"
    b["members"][2]["role"] = None
    b["members"][2]["behaviorId"] = 0
    b["members"][4] = 7
    assert errors_of(b, private=True) == [
        ("password", "invalidType"),
        ("members[0].playerId", "invalidType"),
        ("members[2].role", "invalidType"),
        ("members[2].behaviorId", "outOfRange"),
        ("members[4]", "invalidType"),
        ("coachBehaviorId", "invalidType"),
    ]


def test_password_members_and_coach_errors_together():
    assert errors_of({"members": "x", "coachBehaviorId": 0}, private=True) == [
        ("password", "required"),
        ("members", "invalidType"),
        ("coachBehaviorId", "outOfRange"),
    ]


# --- servicio -----------------------------------------------------------------


class FakeTypedBehaviors:
    """Behaviors del usuario con su tipo. Por defecto 21 y 22 de jugador y 30 de DT."""

    DEFAULT = {21: PLAYER, 22: PLAYER, COACH_ID: COACH}

    def __init__(self, types=None):
        self.types = self.DEFAULT if types is None else types
        self.calls = []

    def behavior_types(self, user_id, ids):
        self.calls.append((user_id, list(ids)))
        return {i: self.types[i] for i in ids if i in self.types}


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def participants_changed(self, league_id):
        self.calls.append(league_id)


def state(**fields):
    base = dict(
        private=False,
        password=None,
        status=LeagueStatus.preparation,
        max_participants=8,
        participants_count=1,
        is_participant=False,
    )
    base.update(fields)
    return LeagueJoinState(**base)


def private_state(**fields):
    return state(private=True, password="secret", **fields)


_BODY = object()


@pytest.fixture()
def repo():
    r = MagicMock(spec=AbstractLeagueRepository)
    r.get_join_state.return_value = state()
    r.join.return_value = None
    return r


def join(repo, players=None, behaviors=None, user_id=2, raw_id="5", raw_body=_BODY):
    service = LeagueService(repo, players or FakePlayers(), behaviors or FakeTypedBehaviors())
    return service.join_league(user_id, "sess-1", raw_id, body() if raw_body is _BODY else raw_body)


def error_of(repo, **kwargs):
    with pytest.raises(ApiError) as exc:
        join(repo, **kwargs)
    return exc.value


def test_service_success_persists_team_and_coach(repo):
    join(repo)
    repo.get_join_state.assert_called_once_with(5, 2)
    data = repo.join.call_args.args[0]
    assert (data.league_id, data.user_id, data.session_id) == (5, 2, "sess-1")
    assert data.coach_behavior_id == COACH_ID
    assert data.unlock_session is False  # liga pública: no hay nada que desbloquear
    assert [(m.player_id, m.behavior_id, m.role) for m in data.members] == [
        (11 + i, 21 + (i % 2), r) for i, r in enumerate(ROLES)
    ]


def test_service_without_coach_persists_none(repo):
    behaviors = FakeTypedBehaviors({21: PLAYER, 22: PLAYER})  # sin behavior de DT
    join(repo, behaviors=behaviors, raw_body={"members": members()})
    assert repo.join.call_args.args[0].coach_behavior_id is None
    assert sorted(behaviors.calls[0][1]) == [21, 22]  # no se consulta un DT inexistente


def test_private_success_unlocks_the_session(repo):
    repo.get_join_state.return_value = private_state()
    join(repo, raw_body=body(password="secret"))
    assert repo.join.call_args.args[0].unlock_session is True


def test_public_league_ignores_a_wrong_password(repo):
    join(repo, raw_body=body(password="cualquiera"))
    repo.join.assert_called_once()


def test_ownership_is_checked_for_the_joining_user_including_the_coach(repo):
    behaviors = FakeTypedBehaviors()
    join(repo, behaviors=behaviors, user_id=2)
    assert len(behaviors.calls) == 1 and behaviors.calls[0][0] == 2
    assert sorted(behaviors.calls[0][1]) == [21, 22, COACH_ID]  # sin duplicar


def test_notifier_is_called_once_after_a_successful_join(repo):
    notifier = FakeNotifier()
    service = LeagueService(repo, FakePlayers(), FakeTypedBehaviors(), notifier=notifier)
    service.join_league(2, "sess-1", "5", body())
    assert notifier.calls == [5]


@pytest.mark.parametrize(
    "join_state, raw_body",
    [
        (None, body()),  # 404
        (state(), {"members": "x"}),  # 400
        (private_state(), body(password="wrong")),  # 403
        (state(is_participant=True), body()),  # 409
    ],
)
def test_notifier_is_not_called_when_the_join_fails(repo, join_state, raw_body):
    repo.get_join_state.return_value = join_state
    notifier = FakeNotifier()
    service = LeagueService(repo, FakePlayers(), FakeTypedBehaviors(), notifier=notifier)
    with pytest.raises(ApiError):
        service.join_league(2, "sess-1", "5", raw_body)
    assert notifier.calls == []


def test_notifier_is_not_called_when_losing_the_race(repo):
    repo.join.return_value = "leagueFull"
    notifier = FakeNotifier()
    service = LeagueService(repo, FakePlayers(), FakeTypedBehaviors(), notifier=notifier)
    with pytest.raises(ApiError):
        service.join_league(2, "sess-1", "5", body())
    assert notifier.calls == []


# -- 404


@pytest.mark.parametrize("raw_id", ["abc", "1.5", "0", "-1", "2147483648", "", " 1", "+1"])
def test_invalid_route_id_is_404_without_touching_the_repo(repo, raw_id):
    err = error_of(repo, raw_id=raw_id)
    assert (err.status_code, err.code) == (404, None)
    repo.get_join_state.assert_not_called()


def test_nonexistent_league_is_404(repo):
    repo.get_join_state.return_value = None
    err = error_of(repo)
    assert (err.status_code, err.code) == (404, None)
    repo.join.assert_not_called()


# -- 403


@pytest.mark.parametrize("password", ["", "wrong", "SECRET", "secret ", " secret"])
def test_wrong_or_empty_password_is_403(repo, password):
    repo.get_join_state.return_value = private_state()
    err = error_of(repo, raw_body=body(password=password))
    assert (err.status_code, err.code) == (403, "invalidLeaguePassword")
    repo.join.assert_not_called()


def test_non_ascii_password_is_compared_correctly(repo):
    repo.get_join_state.return_value = state(private=True, password="contraseña⚽")
    join(repo, raw_body=body(password="contraseña⚽"))
    assert error_of(repo, raw_body=body(password="contrasena⚽")).status_code == 403


# -- 409


@pytest.mark.parametrize(
    "status", [LeagueStatus.started, LeagueStatus.finished, LeagueStatus.cancelled]
)
def test_league_not_in_preparation(repo, status):
    repo.get_join_state.return_value = state(status=status)
    err = error_of(repo)
    assert (err.status_code, err.code) == (409, "notInPreparation")
    repo.join.assert_not_called()


def test_league_full(repo):
    repo.get_join_state.return_value = state(participants_count=8, max_participants=8)
    assert error_of(repo).code == "leagueFull"
    repo.join.assert_not_called()


def test_already_participating(repo):
    repo.get_join_state.return_value = state(is_participant=True)
    assert error_of(repo).code == "alreadyParticipating"
    repo.join.assert_not_called()


@pytest.mark.parametrize(
    "players, behaviors",
    [
        (FakePlayers(owned={11, 12, 13, 14, 15}), None),  # un jugador ajeno o inexistente
        (None, FakeTypedBehaviors({21: PLAYER, COACH_ID: COACH})),  # behavior 22 ajeno
        (None, FakeTypedBehaviors({21: PLAYER, 22: PLAYER})),  # DT ajeno o inexistente
    ],
)
def test_player_or_behavior_not_owned(repo, players, behaviors):
    err = error_of(repo, players=players, behaviors=behaviors)
    assert (err.status_code, err.code) == (409, "playerOrBehaviorNotOwned")
    repo.join.assert_not_called()


@pytest.mark.parametrize(
    "types",
    [
        {21: PLAYER, 22: COACH, COACH_ID: COACH},  # un miembro con behavior de DT
        {21: PLAYER, 22: PLAYER, COACH_ID: PLAYER},  # DT con behavior de jugador
    ],
)
def test_behavior_type_mismatch(repo, types):
    err = error_of(repo, behaviors=FakeTypedBehaviors(types))
    assert (err.status_code, err.code) == (409, "behaviorTypeMismatch")
    repo.join.assert_not_called()


def test_same_behavior_as_member_and_coach_is_a_type_mismatch(repo):
    err = error_of(repo, raw_body=body(coachBehaviorId=21))
    assert err.code == "behaviorTypeMismatch"


def test_losing_the_race_in_the_database_is_reported(repo):
    repo.join.return_value = "leagueFull"  # otro ocupó el último lugar
    err = error_of(repo)
    assert (err.status_code, err.code) == (409, "leagueFull")


# -- precedencia: 404 > 400 > 403 > 409 y orden de los 409


def test_404_beats_400(repo):
    repo.get_join_state.return_value = None
    assert error_of(repo, raw_body={}).status_code == 404
    assert error_of(repo, raw_id="abc", raw_body={}).status_code == 404


def test_400_beats_403(repo):
    repo.get_join_state.return_value = private_state()
    err = error_of(repo, raw_body={"members": [], "password": "wrong"})
    assert (err.status_code, err.code) == (400, "invalidFields")


def test_400_beats_409(repo):
    repo.get_join_state.return_value = state(status=LeagueStatus.started, is_participant=True)
    assert error_of(repo, raw_body={"members": "x"}).status_code == 400


def test_403_beats_409(repo):
    repo.get_join_state.return_value = private_state(
        status=LeagueStatus.started, participants_count=8, is_participant=True
    )
    err = error_of(repo, raw_body=body(password="wrong"), players=FakePlayers(owned=set()))
    assert (err.status_code, err.code) == (403, "invalidLeaguePassword")


def test_403_also_applies_to_participants_and_creator(repo):
    # La contraseña se valida antes de revelar que ya participa
    repo.get_join_state.return_value = private_state(is_participant=True)
    assert error_of(repo, raw_body=body(password="wrong")).status_code == 403


def test_not_in_preparation_beats_league_full(repo):
    repo.get_join_state.return_value = state(
        status=LeagueStatus.started, participants_count=8, max_participants=8
    )
    assert error_of(repo).code == "notInPreparation"


def test_league_full_beats_already_participating(repo):
    repo.get_join_state.return_value = state(
        participants_count=8, max_participants=8, is_participant=True
    )
    assert error_of(repo).code == "leagueFull"


def test_already_participating_beats_not_owned(repo):
    repo.get_join_state.return_value = state(is_participant=True)
    assert error_of(repo, players=FakePlayers(owned=set())).code == "alreadyParticipating"


def test_not_owned_beats_type_mismatch(repo):
    types = {21: COACH, 22: PLAYER}  # 21 de tipo equivocado y el DT ajeno
    assert error_of(repo, behaviors=FakeTypedBehaviors(types)).code == "playerOrBehaviorNotOwned"


# --- endpoint -----------------------------------------------------------------


@pytest.fixture()
def notifier():
    return FakeNotifier()


@pytest.fixture()
def league_api(api, repo, notifier):
    # `api` (conftest) ya resuelve la cookie "valid-session" -> usuario 7
    app.dependency_overrides[get_league_service] = lambda: LeagueService(
        repo, FakePlayers(), FakeTypedBehaviors(), notifier=notifier
    )
    return api


@pytest.fixture()
def auth_league_api(league_api):
    league_api.cookies.set("session_id", "valid-session")
    return league_api


def test_endpoint_success_is_201_without_body_and_notifies(auth_league_api, repo, notifier):
    resp = auth_league_api.post(URL, json=body())
    assert resp.status_code == 201, resp.text
    assert resp.content == b""
    data = repo.join.call_args.args[0]
    assert (data.user_id, data.session_id) == (7, "valid-session")
    assert notifier.calls == [5]


@pytest.mark.parametrize(
    "path, payload",
    [
        (URL, body()),
        ("/leagues/abc/participants", {"members": 5}),
        ("/leagues/0/participants", {}),
        ("/leagues/2147483648/participants", None),
    ],
)
def test_no_cookie_is_401_even_with_bad_id_or_body(league_api, repo, notifier, path, payload):
    resp = league_api.post(path, json=payload)
    assert resp.status_code == 401 and resp.json()["code"] is None
    Error.model_validate(resp.json())
    repo.get_join_state.assert_not_called()
    assert notifier.calls == []


def test_invalid_cookie_is_401(league_api, repo, notifier):
    league_api.cookies.set("session_id", "no-existe")
    resp = league_api.post("/leagues/abc/participants", json={"members": 5})
    assert resp.status_code == 401 and resp.json()["code"] is None
    repo.get_join_state.assert_not_called()


@pytest.mark.parametrize("raw_id", ["abc", "1.5", "0", "-1", "2147483648", "99999999999999999999"])
def test_invalid_route_id_is_404_never_422(auth_league_api, repo, notifier, raw_id):
    for kwargs in ({"json": body()}, {"json": {"members": 5}}, {}):
        resp = auth_league_api.post(f"/leagues/{raw_id}/participants", **kwargs)
        assert resp.status_code == 404 and resp.json()["code"] is None
        Error.model_validate(resp.json())
    repo.get_join_state.assert_not_called()
    assert notifier.calls == []


def test_endpoint_nonexistent_league_is_404(auth_league_api, repo, notifier):
    repo.get_join_state.return_value = None
    resp = auth_league_api.post(URL, json={"members": 5})
    assert resp.status_code == 404
    assert resp.json() == {"code": None, "message": "La liga no existe."}
    assert notifier.calls == []


@pytest.mark.parametrize(
    "kwargs, private, errors",
    [
        ({}, False, [("members", "required")]),
        ({}, True, [("password", "required"), ("members", "required")]),
        (
            {"content": "{", "headers": {"Content-Type": "application/json"}},
            True,
            [("password", "required"), ("members", "required")],
        ),
        ({"json": []}, False, [("members", "required")]),
        ({"json": "x"}, False, [("members", "required")]),
        ({"json": {"members": "x"}}, False, [("members", "invalidType")]),
        ({"json": {"members": []}}, False, [("members", "invalidTeam")]),
        (
            {"json": {"members": members(), "coachBehaviorId": "x", "password": 5}},
            True,
            [("password", "invalidType"), ("coachBehaviorId", "invalidType")],
        ),
    ],
)
def test_body_errors_are_400_invalid_fields_never_422(
    auth_league_api, repo, notifier, kwargs, private, errors
):
    repo.get_join_state.return_value = private_state() if private else state()
    resp = auth_league_api.post(URL, **kwargs)
    assert resp.status_code == 400, resp.text
    payload = resp.json()
    ValidationBadRequest.model_validate(payload)
    assert payload["code"] == "invalidFields" and payload["message"]
    assert [(e["field"], e["reason"]) for e in payload["errors"]] == errors
    repo.join.assert_not_called()
    assert notifier.calls == []


def test_endpoint_wrong_password_is_403(auth_league_api, repo, notifier):
    repo.get_join_state.return_value = private_state()
    resp = auth_league_api.post(URL, json=body(password="wrong"))
    assert resp.status_code == 403
    JoinLeagueForbidden.model_validate(resp.json())
    assert resp.json()["code"] == "invalidLeaguePassword"
    assert notifier.calls == []


@pytest.mark.parametrize(
    "join_state, code",
    [
        (state(status=LeagueStatus.started), "notInPreparation"),
        (state(participants_count=8), "leagueFull"),
        (state(is_participant=True), "alreadyParticipating"),
    ],
)
def test_endpoint_conflicts_are_409_and_publish_nothing(
    auth_league_api, repo, notifier, join_state, code
):
    repo.get_join_state.return_value = join_state
    resp = auth_league_api.post(URL, json=body())
    assert resp.status_code == 409
    JoinLeagueConflict.model_validate(resp.json())
    assert resp.json()["code"] == code
    assert notifier.calls == []
