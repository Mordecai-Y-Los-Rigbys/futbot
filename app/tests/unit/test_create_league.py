import pytest

from app.schemas.errors import ValidationBadRequest
from app.tests.unit.member_cases import MEMBERS_IDS, MEMBERS_PARAMS, MISSING, TEAM, err

REQUIRED = ["name", "minParticipants", "maxParticipants", "matchDuration", "private", "members"]


def payload(**over):
    p = {
        "name": "Liga",
        "minParticipants": 3,
        "maxParticipants": 8,
        "matchDuration": 5,
        "private": False,
        "members": [dict(m) for m in TEAM],
    }
    for k, v in over.items():
        if v is MISSING:
            p.pop(k, None)  # si la clave no estaba en el base, ya "falta"
        else:
            p[k] = v
    return p


def post(api, body):
    return api.post("/leagues", json=body)


def assert_errors(resp, expected):
    assert resp.status_code == 400
    body = resp.json()
    ValidationBadRequest.model_validate(body)
    assert body["code"] == "invalidFields"
    assert body["message"]
    assert body["errors"] == expected


# --- éxito --------------------------------------------------------------------


def test_creates_public_league(auth_api, fake_repo):
    resp = post(auth_api, payload(password="ignorada"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "preparation"
    assert body["participantsCount"] == 1
    data = fake_repo.created[0]
    assert data.creator_id == 7
    assert data.password is None  # pública: se ignora y no se persiste
    assert [m.role for m in data.members] == [m["role"] for m in TEAM]


def test_private_league_stores_the_password_as_sent(auth_api, fake_repo):
    resp = post(auth_api, payload(private=True, password="secret"))
    assert resp.status_code == 201
    assert fake_repo.created[0].private is True
    assert fake_repo.created[0].password == "secret"


@pytest.mark.parametrize("pw", [123, "x" * 100, None, ""])
def test_public_league_ignores_password_entirely(auth_api, fake_repo, pw):
    assert post(auth_api, payload(password=pw)).status_code == 201
    assert fake_repo.created[0].password is None


def test_league_without_allow_draws_is_created_in_normal_mode(auth_api, fake_repo):
    resp = post(auth_api, payload())
    assert resp.status_code == 201
    assert fake_repo.created[0].allow_draws is True


def test_boundaries_are_valid(auth_api):
    ok = payload(name="x" * 20, minParticipants=3, maxParticipants=3, matchDuration=10)
    assert post(auth_api, ok).status_code == 201
    ok = payload(private=True, password="x" * 72, matchDuration=1)
    assert post(auth_api, ok).status_code == 201
    ok = payload(minParticipants=2147483647, maxParticipants=2147483647)
    assert post(auth_api, ok).status_code == 201


# --- un reason por campo --------------------------------------------------------

FIELD_CASES = [
    ({"name": MISSING}, [err("name", "required")]),
    ({"name": ""}, [err("name", "required")]),
    ({"name": 123}, [err("name", "invalidType")]),
    ({"name": None}, [err("name", "invalidType")]),
    ({"name": "x" * 21}, [err("name", "tooLong")]),
    ({"minParticipants": MISSING}, [err("minParticipants", "required")]),
    ({"minParticipants": "3"}, [err("minParticipants", "invalidType")]),
    ({"minParticipants": 3.0}, [err("minParticipants", "invalidType")]),
    ({"minParticipants": True}, [err("minParticipants", "invalidType")]),
    ({"minParticipants": None}, [err("minParticipants", "invalidType")]),
    ({"minParticipants": 2}, [err("minParticipants", "outOfRange")]),
    ({"minParticipants": 2147483648}, [err("minParticipants", "outOfRange")]),
    ({"maxParticipants": MISSING}, [err("maxParticipants", "required")]),
    ({"maxParticipants": "8"}, [err("maxParticipants", "invalidType")]),
    ({"maxParticipants": None}, [err("maxParticipants", "invalidType")]),
    ({"maxParticipants": 2147483648}, [err("maxParticipants", "outOfRange")]),
    ({"minParticipants": 5, "maxParticipants": 4}, [err("maxParticipants", "lessThanMin")]),
    ({"matchDuration": MISSING}, [err("matchDuration", "required")]),
    ({"matchDuration": "5"}, [err("matchDuration", "invalidType")]),
    ({"matchDuration": 1.5}, [err("matchDuration", "invalidType")]),
    ({"matchDuration": 0}, [err("matchDuration", "outOfRange")]),
    ({"matchDuration": 11}, [err("matchDuration", "outOfRange")]),
    ({"private": MISSING}, [err("private", "required")]),
    ({"private": "yes"}, [err("private", "invalidType")]),
    ({"private": None}, [err("private", "invalidType")]),
    ({"private": 1}, [err("private", "invalidType")]),
    ({"private": True, "password": MISSING}, [err("password", "required")]),
    ({"private": True, "password": None}, [err("password", "required")]),
    ({"private": True, "password": ""}, [err("password", "required")]),
    ({"private": True, "password": 123}, [err("password", "invalidType")]),
    ({"private": True, "password": "x" * 73}, [err("password", "tooLong")]),
    ({"allowDraws": None}, [err("allowDraws", "invalidType")]),
    ({"allowDraws": "false"}, [err("allowDraws", "invalidType")]),
    ({"allowDraws": 0}, [err("allowDraws", "invalidType")]),
]


@pytest.mark.parametrize("over, expected", FIELD_CASES)
def test_field_reasons(auth_api, fake_repo, over, expected):
    assert_errors(post(auth_api, payload(**over)), expected)
    assert fake_repo.created == []


@pytest.mark.parametrize("members, expected", MEMBERS_PARAMS, ids=MEMBERS_IDS)
def test_members_reasons(auth_api, fake_repo, members, expected):
    assert_errors(post(auth_api, payload(members=members)), expected)
    assert fake_repo.created == []


# --- reglas que cruzan campos y orden -----------------------------------------


@pytest.mark.parametrize(
    "over",
    [
        {"minParticipants": 2, "maxParticipants": 1},  # min inválido
        {"minParticipants": 5, "maxParticipants": "1"},  # max inválido
    ],
)
def test_less_than_min_needs_both_fields_valid(auth_api, over):
    resp = post(auth_api, payload(**over))
    assert all(e["reason"] != "lessThanMin" for e in resp.json()["errors"])


@pytest.mark.parametrize("private", [False, "yes", MISSING])
def test_password_is_not_evaluated_unless_private_is_true(auth_api, private):
    resp = post(auth_api, payload(private=private, password=123))
    errors = resp.json().get("errors", [])
    assert all(e["field"] != "password" for e in errors)


def test_all_failures_are_reported_in_schema_order(auth_api):
    body = payload(
        name="x" * 21,
        minParticipants=1,
        maxParticipants="x",
        matchDuration=99,
        private=True,
        password="",
        allowDraws="si",
        members=TEAM[:5],
    )
    assert_errors(
        post(auth_api, body),
        [
            err("name", "tooLong"),
            err("minParticipants", "outOfRange"),
            err("maxParticipants", "invalidType"),
            err("matchDuration", "outOfRange"),
            err("password", "required"),
            err("allowDraws", "invalidType"),
            err("members", "invalidTeam"),
        ],
    )


def test_less_than_min_takes_the_place_of_max_participants(auth_api):
    body = payload(name=5, minParticipants=5, maxParticipants=4, matchDuration=0)
    assert_errors(
        post(auth_api, body),
        [
            err("name", "invalidType"),
            err("maxParticipants", "lessThanMin"),
            err("matchDuration", "outOfRange"),
        ],
    )


def test_400_has_priority_over_409(auth_api, fake_players):
    fake_players.owned = set()
    resp = post(auth_api, payload(members=TEAM[:5]))
    assert resp.status_code == 400


# --- 409 / 401 / body ilegible --------------------------------------------------


def test_not_owned_returns_409(auth_api, fake_repo, fake_players):
    fake_players.owned = set()
    resp = post(auth_api, payload())
    assert resp.status_code == 409
    assert resp.json()["code"] == "playerOrBehaviorNotOwned"
    assert fake_repo.created == []


def test_no_session_returns_401_even_with_broken_body(api):
    resp = api.post("/leagues", content="{", headers={"Content-Type": "application/json"})
    assert resp.status_code == 401
    assert resp.json()["code"] is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {},  # sin body
        {"content": "{", "headers": {"Content-Type": "application/json"}},
        {"json": [1, 2]},
        {"json": "texto"},
        {"json": 42},
        {"json": {}},
    ],
)
def test_unreadable_body_reports_every_required_field(auth_api, fake_repo, kwargs):
    resp = auth_api.post("/leagues", **kwargs)
    assert_errors(resp, [err(f, "required") for f in REQUIRED])
    assert fake_repo.created == []
