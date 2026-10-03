import pytest

MISSING = object()

TEAM = [
    {"playerId": 1, "behaviorId": 1, "role": "forward"},
    {"playerId": 2, "behaviorId": 1, "role": "midfield"},
    {"playerId": 3, "behaviorId": 1, "role": "defense"},
    {"playerId": 4, "behaviorId": 1, "role": "substitute"},
    {"playerId": 5, "behaviorId": 1, "role": "substitute"},
    {"playerId": 6, "behaviorId": 1, "role": "substitute"},
]


def payload(**over):
    p = {
        "name": "Liga",
        "minParticipants": 3,
        "maxParticipants": 8,
        "matchDuration": 5,
        "private": False,
        "members": TEAM,
    }
    for k, v in over.items():
        if v is MISSING:
            p.pop(k, None)  # si la clave no estaba en el base, ya "falta"
        else:
            p[k] = v
    return p


def team(i, **changes):
    """TEAM con el miembro i modificado (MISSING borra la clave)."""
    out = [dict(m) for m in TEAM]
    for k, v in changes.items():
        if v is MISSING:
            out[i].pop(k)
        else:
            out[i][k] = v
    return out


def post(api, body):
    return api.post("/leagues", json=body)


# --- éxito ---------------------------------------------------------------

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


# --- 400 por código --------------------------------------------------------

CASES = [
    # invalidFieldType
    ({"name": 123}, "invalidFieldType"),
    ({"name": None}, "invalidFieldType"),
    ({"minParticipants": "3"}, "invalidFieldType"),
    ({"minParticipants": 3.0}, "invalidFieldType"),
    ({"minParticipants": True}, "invalidFieldType"),
    ({"maxParticipants": 2147483648}, "invalidFieldType"),
    ({"matchDuration": "5"}, "invalidFieldType"),
    ({"private": "yes"}, "invalidFieldType"),
    ({"private": True, "password": 123}, "invalidFieldType"),
    ({"members": "x"}, "invalidFieldType"),
    ({"members": TEAM[:5] + ["x"]}, "invalidFieldType"),
    ({"members": team(0, playerId="abc")}, "invalidFieldType"),
    ({"members": team(0, playerId=0)}, "invalidFieldType"),
    ({"members": team(0, behaviorId=2147483648)}, "invalidFieldType"),
    ({"members": team(0, role=5)}, "invalidFieldType"),
    # incompleteForm
    ({"name": MISSING}, "incompleteForm"),
    ({"minParticipants": MISSING}, "incompleteForm"),
    ({"maxParticipants": MISSING}, "incompleteForm"),
    ({"matchDuration": MISSING}, "incompleteForm"),
    ({"private": MISSING}, "incompleteForm"),
    ({"members": MISSING}, "incompleteForm"),
    ({"private": True, "password": MISSING}, "incompleteForm"),
    ({"private": True, "password": None}, "incompleteForm"),
    ({"private": True, "password": ""}, "incompleteForm"),
    ({"members": team(0, behaviorId=MISSING)}, "incompleteForm"),
    # contenido
    ({"name": "x" * 21}, "nameTooLong"),
    ({"minParticipants": 2}, "minParticipantsTooLow"),
    ({"minParticipants": 5, "maxParticipants": 4}, "maxLessThanMin"),
    ({"matchDuration": 0}, "matchDurationOutOfRange"),
    ({"matchDuration": 11}, "matchDurationOutOfRange"),
    ({"private": True, "password": "x" * 73}, "passwordTooLong"),
    # invalidTeam
    ({"members": TEAM[:5]}, "invalidTeam"),
    ({"members": TEAM + [TEAM[0]]}, "invalidTeam"),
    ({"members": team(0, role="goalkeeper")}, "invalidTeam"),
    ({"members": team(3, role="forward")}, "invalidTeam"),
    ({"members": team(1, playerId=1)}, "invalidTeam"),
]


@pytest.mark.parametrize("over, code", CASES)
def test_invalid_payload_returns_400_with_code(auth_api, fake_repo, over, code):
    resp = post(auth_api, payload(**over))
    assert resp.status_code == 400
    assert resp.json()["code"] == code
    assert resp.json()["message"]
    assert fake_repo.created == []


def test_boundaries_are_valid(auth_api):
    ok = payload(name="x" * 20, minParticipants=3, maxParticipants=3, matchDuration=10)
    assert post(auth_api, ok).status_code == 201
    ok = payload(private=True, password="x" * 72, matchDuration=1)
    assert post(auth_api, ok).status_code == 201


# --- orden de evaluación (convención 6) -----------------------------------------------

def test_type_error_beats_missing_field(auth_api):
    resp = post(auth_api, payload(name=MISSING, matchDuration="x"))
    assert resp.json()["code"] == "invalidFieldType"


def test_incomplete_beats_content_rules(auth_api):
    resp = post(auth_api, payload(members=MISSING, name="x" * 99))
    assert resp.json()["code"] == "incompleteForm"


def test_content_rules_follow_enum_order(auth_api):
    resp = post(auth_api, payload(name="x" * 99, minParticipants=1, matchDuration=99))
    assert resp.json()["code"] == "nameTooLong"
    resp = post(auth_api, payload(minParticipants=1, matchDuration=99))
    assert resp.json()["code"] == "minParticipantsTooLow"


def test_invalid_team_is_the_last_400(auth_api):
    resp = post(auth_api, payload(matchDuration=0, members=TEAM[:5]))
    assert resp.json()["code"] == "matchDurationOutOfRange"


def test_400_has_priority_over_409(auth_api, fake_teams):
    fake_teams.owned_players = set()
    resp = post(auth_api, payload(members=TEAM[:5]))
    assert resp.status_code == 400


# --- 409 / 401 / body raro ----------------------------------------------------------------

def test_not_owned_returns_409(auth_api, fake_repo, fake_teams):
    fake_teams.owned_players = set()
    resp = post(auth_api, payload())
    assert resp.status_code == 409
    assert resp.json()["code"] == "playerOrBehaviorNotOwned"
    assert fake_repo.created == []


def test_no_session_returns_401_even_with_broken_body(api):
    resp = api.post("/leagues", content="{", headers={"Content-Type": "application/json"})
    assert resp.status_code == 401
    assert resp.json()["code"] is None


def test_malformed_json_returns_400(auth_api):
    resp = auth_api.post("/leagues", content="{", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalidFieldType"


def test_non_object_body_returns_400(auth_api):
    assert post(auth_api, [1, 2]).json()["code"] == "invalidFieldType"


def test_empty_body_is_incomplete_form(auth_api):
    assert auth_api.post("/leagues").json()["code"] == "incompleteForm"