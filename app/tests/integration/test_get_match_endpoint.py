from datetime import datetime, timedelta, timezone

import pytest

from app.models.match import Match, MatchStatus
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository

pytestmark = pytest.mark.integration

SCHEDULED = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
MATCH_KEYS = {
    "id", "leagueId", "name", "status", "club1", "club2", "scheduledAt", "createdAt", "result"
}


@pytest.fixture()
def owner(create_user):
    return create_user("owner", avatar=2)


@pytest.fixture()
def rival(create_user):
    return create_user("rival", avatar=4)


@pytest.fixture()
def outsider(create_user):
    return create_user("outsider")


@pytest.fixture()
def make_match(db_session):
    def _make(**fields) -> Match:
        match = Match(**fields)
        db_session.add(match)
        db_session.commit()
        return match
    
    return _make


@pytest.fixture()
def waiting_friendly(make_match, owner):
    return make_match(
        user_1_id=owner.id,
        name="Amistoso"
    )


@pytest.fixture()
def friendly(make_match, owner, rival):
    return make_match(
        user_1_id=owner.id,
        user_2_id=rival.id,
        name="Amistoso"
    )


@pytest.fixture()
def league_match(make_league, add_participant, make_match, owner, rival):
    
    def _make(private:bool) -> Match:
        league = make_league(owner, status="started", private=private)
        add_participant(league, rival)
        return make_match(
            league_id=league.id,
            user_1_id=owner.id,
            user_2_id=rival.id,
            scheduled_at=SCHEDULED
        )
    
    return _make


@pytest.mark.parametrize("raw_id", ["existing", "999999", "abc"])
def test_no_session_is_401(client, friendly, raw_id):
    match_id = friendly.id if raw_id == "existing" else raw_id
    r = client.get(f"/matches/{match_id}")
    assert r.status_code == 401 and r.json()["code"] is None


def test_expired_session_is_401(login_as, owner, friendly):
    api = login_as(owner, expires_in=timedelta(days=-1))
    assert api.get(f"/matches/{friendly.id}").status_code == 401
    

@pytest.mark.parametrize("bad", ["999999", "abc", "0", "2147483648"])
def test_missing_or_invalid_id_is_404_before_403(login_as, outsider, bad):
    r = login_as(outsider).get(f"/matches/{bad}")
    assert r.status_code == 404 and r.json()["code"] is None
    

def test_waiting_friendly_for_its_creator(login_as, owner, waiting_friendly):
    r = login_as(owner).get(f"/matches/{waiting_friendly.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["club2"] is None and body["result"] is None
    assert body["leagueId"] is None and body["scheduledAt"] is None
    assert (body["status"], body["name"]) == ("scheduled", "Amistoso")
    

@pytest.mark.parametrize("who", ["owner", "rival"])
def test_friendly_with_rival_for_both_players(request, login_as, owner, rival, friendly, who):
    user = request.getfixturevalue(who)
    r = login_as(user).get(f"/matches/{friendly.id}")
    assert r.status_code == 200
    assert r.json()["club1"] == {
        "id": owner.id, "username": "owner", "name": "club-owner", "avatar": 2
    }
    assert r.json()["club2"] == {
        "id": rival.id, "username": "rival", "name": "club-rival", "avatar": 4
    }


@pytest.mark.parametrize("match_fixture", ["waiting_friendly", "friendly"])
def test_friendly_outsider_is_403(request, login_as, outsider, match_fixture):
    match = request.getfixturevalue(match_fixture)
    r = login_as(outsider).get(f"/matches/{match.id}")
    assert r.status_code == 403 and r.json()["code"] == "notAPlayerInMatch"
    

def test_finished_match_has_result(login_as, owner, rival, make_match):
    match = make_match(
        user_1_id=owner.id, user_2_id=rival.id, name="Amistoso",
        status=MatchStatus.finished, score_1=2, score_2=1,
    )
    r = login_as(owner).get(f"/matches/{match.id}")
    assert r.json()["result"] == {"score1": 2, "score2": 1, "penalties": None}


def test_public_league_match_for_outsider(login_as, outsider, league_match):
    match = league_match(private=False)
    r = login_as(outsider).get(f"/matches/{match.id}")
    assert r.status_code == 200
    assert r.json()["leagueId"] == match.league_id
    

@pytest.mark.parametrize("who", ["owner", "rival"])
def test_private_league_members_get_the_match(request, login_as, league_match, who):
    match = league_match(private=True)
    r = login_as(request.getfixturevalue(who)).get(f"/matches/{match.id}")
    assert r.status_code == 200


def test_private_league_participant_not_playing_gets_the_match(
    login_as, create_user, add_participant, league_match, db_session
):
    match = league_match(private=True)
    third = create_user("third")
    add_participant(match.league, third)
    assert login_as(third).get(f"/matches/{match.id}").status_code == 200


def test_private_league_creator_not_playing_gets_the_match(
    login_as, create_user, make_league, add_participant, make_match, owner, rival
):
    league = make_league(owner, status="started", private=True)
    third = create_user("third")
    add_participant(league, rival)
    add_participant(league, third)
    match = make_match(
        league_id=league.id,
        user_1_id=rival.id,
        user_2_id=third.id,
        scheduled_at=SCHEDULED,
    )
    r = login_as(owner).get(f"/matches/{match.id}")
    assert r.status_code == 200
    assert "secret" not in r.text


def test_private_league_outsider_is_403(login_as, outsider, league_match):
    match = league_match(private=True)
    r = login_as(outsider).get(f"/matches/{match.id}")
    assert r.status_code == 403 and r.json()["code"] == "leagueAccessRequired"
    assert "secret" not in r.text
    

def test_private_league_outsider_after_unlock_gets_the_match(login_as, outsider, league_match):
    match = league_match(private=True)
    api = login_as(outsider)
    assert api.post(f"/leagues/{match.league_id}/access", json={"password": "secret"}).status_code == 204
    r = api.get(f"/matches/{match.id}")
    assert r.status_code == 200
    assert "secret" not in r.text
    

def test_unlock_does_not_carry_to_another_session(login_as, outsider, league_match):
    match = league_match(private=True)
    first, second = login_as(outsider), login_as(outsider)
    first.post(f"/leagues/{match.league_id}/access", json={"password": "secret"})
    assert first.get(f"/matches/{match.id}").status_code == 200
    r = second.get(f"/matches/{match.id}")
    assert r.status_code == 403 and r.json()["code"] == "leagueAccessRequired"


def test_league_match_body_has_only_contract_fields(login_as, owner, league_match):
    match = league_match(private=True)
    r = login_as(owner).get(f"/matches/{match.id}")
    assert set(r.json()) == MATCH_KEYS
    assert r.json()["scheduledAt"] == "2026-11-20T18:00:00Z"
    assert "secret" not in r.text
    