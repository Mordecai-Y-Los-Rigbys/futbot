from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.player import Player
from app.models.session import UserSession
from app.models.session_league_unlock import SessionLeagueUnlock
from app.repositories.league_access_sqlalchemy import SqlAlchemyLeagueAccessRepository
from app.services.league_access_service import has_league_access

pytestmark = pytest.mark.integration


@pytest.fixture()
def access_case(create_user, make_league, login_as, db_session):
    creator = create_user("owner")
    outsider = create_user("outsider")
    league = make_league(creator, private=True)
    return league, outsider, login_as(outsider)


def unlocked(db_session, api, league):
    return SqlAlchemyLeagueAccessRepository(db_session).is_unlocked(
        api.cookies.get("session_id"), league.id
    )


def allowed(db_session, api, user, league):
    repo = SqlAlchemyLeagueAccessRepository(db_session)
    return has_league_access(
        api.cookies.get("session_id"), user.id, repo.get_league(league.id), repo
    )


@pytest.mark.parametrize(
    "raw", ["", "{", "null", "[]", "123", '"secret"', "{}", '{"password":null}', '{"other":1}']
)
def test_required(access_case, raw, db_session):
    league, _, api = access_case
    response = api.post(f"/leagues/{league.id}/access", content=raw)
    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert response.json()["errors"] == [{"field": "password", "reason": "required"}]
    assert not unlocked(db_session, api, league)


@pytest.mark.parametrize("password", [123, False, [], {}])
def test_invalid_type(access_case, password, db_session):
    league, _, api = access_case
    response = api.post(f"/leagues/{league.id}/access", json={"password": password})
    assert response.status_code == 400
    assert response.json()["code"] == "invalidFields"
    assert response.json()["errors"] == [{"field": "password", "reason": "invalidType"}]
    assert not unlocked(db_session, api, league)


@pytest.mark.parametrize("password", ["", "wrong", " secret", "secret ", "SECRET", "a" * 1000])
def test_wrong_password(access_case, password, db_session):
    league, _, api = access_case
    response = api.post(f"/leagues/{league.id}/access", json={"password": password})
    assert response.status_code == 403
    assert response.json()["code"] == "invalidLeaguePassword"
    assert not unlocked(db_session, api, league)


@pytest.mark.parametrize("raw_id", ["abc", "0", "-1", "1.5", "2147483648", "2147483647"])
def test_404_before_body_validation(access_case, raw_id):
    _, _, api = access_case
    assert api.post(f"/leagues/{raw_id}/access", content="{").status_code == 404


@pytest.mark.parametrize("cookie", [None, "invalid"])
def test_401_before_id_and_body(client, cookie):
    client.cookies.clear()
    if cookie:
        client.cookies.set("session_id", cookie)
    assert client.post("/leagues/abc/access", content="{").status_code == 401


def test_unlock_is_idempotent_and_isolated(
    access_case, db_session, login_as, make_league, create_user
):
    league, user, api = access_case
    another_session = login_as(user)
    another_league = make_league(create_user("owner2"), private=True)
    assert not allowed(db_session, api, user, league)
    response = api.post(f"/leagues/{league.id}/access", json={"password": "secret"})
    assert response.status_code == 204 and response.content == b""
    assert "set-cookie" not in response.headers
    assert allowed(db_session, api, user, league)
    assert not allowed(db_session, another_session, user, league)
    assert not allowed(db_session, api, user, another_league)
    for raw in ['{"password":"secret"}', '{"password":"wrong"}', "{", ""]:
        assert api.post(f"/leagues/{league.id}/access", content=raw).status_code == 204
    assert db_session.scalar(select(func.count()).select_from(SessionLeagueUnlock)) == 1


@pytest.mark.parametrize("role", ["creator", "participant", "public"])
@pytest.mark.parametrize("raw", ["", "{", '{"password":123}', '{"password":"wrong"}'])
def test_body_ignored(role, raw, create_user, make_league, add_participant, login_as, db_session):
    creator, user = create_user("owner"), create_user("reader")
    league = make_league(creator, private=role != "public")
    if role == "creator":
        user = creator
    elif role == "participant":
        add_participant(league, user)
    api = login_as(user)
    response = api.post(f"/leagues/{league.id}/access", content=raw)
    assert response.status_code == 204 and response.content == b""
    assert unlocked(db_session, api, league) == (role != "public")


@pytest.mark.parametrize("unlock_first", [False, True])
def test_leave_preserves_only_existing_unlock(
    access_case, db_session, add_participant, unlock_first
):
    league, user, api = access_case
    add_participant(league, user)
    assert allowed(db_session, api, user, league)
    if unlock_first:
        assert api.post(f"/leagues/{league.id}/access", content="{").status_code == 204
    assert api.delete(f"/leagues/{league.id}/participants/me").status_code == 204
    assert unlocked(db_session, api, league) == unlock_first
    assert allowed(db_session, api, user, league) == unlock_first


def test_creator_unlock_does_not_allow_leaving(create_user, make_league, login_as, db_session):
    creator = create_user("owner")
    league = make_league(creator, private=True)
    api = login_as(creator)
    assert api.post(f"/leagues/{league.id}/access").status_code == 204
    response = api.delete(f"/leagues/{league.id}/participants/me")
    assert response.status_code == 409 and response.json()["code"] == "isCreator"
    assert unlocked(db_session, api, league)


@pytest.mark.parametrize("expired", [False, True], ids=["logout", "vencimiento"])
def test_session_end_removes_unlocks(access_case, db_session, login_as, expired):
    league, user, api = access_case
    other = login_as(user)
    access_url = f"/leagues/{league.id}/access"
    participants_url = f"/leagues/{league.id}/participants"

    for active_client in (api, other):
        response = active_client.post(access_url, json={"password": "secret"})
        assert response.status_code == 204

    sid = api.cookies["session_id"]

    if expired:
        session = db_session.get(UserSession, sid)
        session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_session.commit()
    else:
        assert api.post("/auth/log-out").status_code == 204

    replay = api.get(participants_url, headers={"Cookie": f"session_id={sid}"})
    assert replay.status_code == 401
    assert replay.json()["code"] is None
    assert db_session.get(SessionLeagueUnlock, (sid, league.id)) is None

    assert unlocked(db_session, other, league)
    assert other.get(participants_url).status_code == 200


def test_login_after_logout_requires_unlock_again(client, create_user, make_league):
    league = make_league(create_user("owner"), private=True)
    access_url = f"/leagues/{league.id}/access"
    participants_url = f"/leagues/{league.id}/participants"
    credentials = {"email": "reader@example.com", "password": "securepassword"}

    registered = client.post(
        "/auth/register",
        json={
            **credentials,
            "username": "reader",
            "clubName": "Club Reader",
            "avatar": 1,
        },
    )
    assert registered.status_code == 201
    old_sid = client.cookies["session_id"]

    assert client.post(access_url, json={"password": "secret"}).status_code == 204
    assert client.get(participants_url).status_code == 200

    assert client.post("/auth/log-out").status_code == 204
    assert "session_id" not in client.cookies

    assert client.post("/auth/log-in", json=credentials).status_code == 200
    assert client.cookies["session_id"] != old_sid

    denied = client.get(participants_url)
    assert denied.status_code == 403
    assert denied.json()["code"] == "leagueAccessRequired"

    assert client.post(access_url, json={"password": "secret"}).status_code == 204
    assert client.get(participants_url).status_code == 200
    
    
def test_unicode_password(access_case, db_session):
    league, _, api = access_case
    league.password = "ñ🔐"
    db_session.commit()
    assert api.post(f"/leagues/{league.id}/access", json={"password": "ñ🔐"}).status_code == 204


def test_detail_stays_public_to_authenticated_users(access_case, db_session):
    league, _, api = access_case
    response = api.get(f"/leagues/{league.id}")
    assert response.status_code == 200
    assert "password" not in response.json()
    assert not unlocked(db_session, api, league)


ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


def team_of(db_session, make_behaviors, user):
    """Body válido de inscripción: 6 jugadores y behaviors de jugador del usuario."""
    players = [
        Player(
            user_id=user.id, name=f"J{i}", power=60, agility=60, control=60, strength=60, speed=60
        )
        for i in range(6)
    ]
    db_session.add_all(players)
    db_session.commit()
    behaviors = make_behaviors(user.id, [f"b{user.id}-{i}" for i in range(6)])
    return {
        "members": [
            {"playerId": p.id, "role": r, "behaviorId": b.id}
            for p, r, b in zip(players, ROLES, behaviors)
        ]
    }


def test_join_unlocks_and_leaving_keeps_access(access_case, db_session, make_behaviors):
    league, user, api = access_case
    body = {**team_of(db_session, make_behaviors, user), "password": "secret"}

    assert api.post(f"/leagues/{league.id}/participants", json=body).status_code == 201
    assert unlocked(db_session, api, league)
    assert api.delete(f"/leagues/{league.id}/participants/me").status_code == 204

    # Ya no participa, pero la sesión conserva el desbloqueo de la inscripción:
    # /access no evalúa la contraseña.
    assert allowed(db_session, api, user, league)
    assert api.post(f"/leagues/{league.id}/access", json={"password": "wrong"}).status_code == 204


def test_leaving_from_another_session_loses_access(
    access_case, db_session, make_behaviors, login_as
):
    league, user, joined_session = access_case
    body = {**team_of(db_session, make_behaviors, user), "password": "secret"}
    assert joined_session.post(f"/leagues/{league.id}/participants", json=body).status_code == 201

    other_session = login_as(user)  # nunca desbloqueó la liga
    assert other_session.delete(f"/leagues/{league.id}/participants/me").status_code == 204

    assert not allowed(db_session, other_session, user, league)
    response = other_session.post(f"/leagues/{league.id}/access", json={"password": "wrong"})
    assert response.status_code == 403
    assert response.json()["code"] == "invalidLeaguePassword"
    assert allowed(db_session, joined_session, user, league)  # la otra sesión sí lo conserva


def test_access_openapi_contract():
    from app.main import app

    operation = app.openapi()["paths"]["/leagues/{id}/access"]["post"]
    assert operation["operationId"] == "unlockLeague"
    assert {"204", "400", "401", "403", "404"} <= operation["responses"].keys()
    assert "content" not in operation["responses"]["204"]
    assert operation["requestBody"]["required"] is False
