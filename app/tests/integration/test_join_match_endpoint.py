from datetime import datetime, timedelta, timezone

import pytest

from app.models.match import Match, MatchStatus
from app.models.match_ws_token import MatchWsToken
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository
from app.repositories.match_ws_token_sqlalchemy import SqlAlchemyMatchWsTokenRepository
from app.services.match_handshake_service import MatchHandshakeService

pytestmark = pytest.mark.integration


@pytest.fixture()
def creator(create_user):
    return create_user("creator")


@pytest.fixture()
def waiting(db_session, creator):
    m = Match(user_1_id=creator.id, name="Amistoso")
    db_session.add(m)
    db_session.commit()
    return m


def test_creator_gets_token_without_rival_and_it_passes_the_handshake(
    login_as, creator, waiting, db_session
):
    r = login_as(creator).post(f"/matches/{waiting.id}/connections")
    assert r.status_code == 201
    token = r.json()["tokenWs"]

    row = db_session.get(MatchWsToken, token)
    assert (row.user_id, row.match_id) == (creator.id, waiting.id)

    service = MatchHandshakeService(
        SqlAlchemyMatchWsTokenRepository(db_session), SqlAlchemyMatchRepository(db_session)
    )
    grant = service.authorize(token, str(waiting.id))
    assert (grant.user_id, grant.match_id) == (creator.id, waiting.id)
    db_session.refresh(waiting)
    assert waiting.status == MatchStatus.scheduled and waiting.user_2_id is None


def test_cancelled_match_is_409_and_creates_no_token(login_as, creator, waiting, db_session):
    waiting.status = MatchStatus.cancelled
    db_session.commit()
    r = login_as(creator).post(f"/matches/{waiting.id}/connections")
    assert r.status_code == 409 and r.json()["code"] == "matchCancelled"
    assert db_session.query(MatchWsToken).count() == 0


def test_no_session_is_401(client, waiting):
    assert client.post(f"/matches/{waiting.id}/connections").status_code == 401


@pytest.fixture()
def league_match(db_session, create_user, make_league):
    owner, rival = create_user("owner"), create_user("rival")
    league = make_league(owner, "Privada", status="started", private=True)  # password "secret"
    m = Match(
        league_id=league.id, user_1_id=owner.id, user_2_id=rival.id,
        status=MatchStatus.started,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(m)
    db_session.commit()
    return m


def test_private_league_outsider_flow(login_as, create_user, league_match):
    api = login_as(create_user("outsider"))
    url = f"/matches/{league_match.id}/connections"
    assert api.post(url, json={"password": 1}).json()["code"] == "invalidFieldType"
    assert api.post(url, json={"password": "mala"}).status_code == 403
    assert api.post(url, json={"password": "secret"}).status_code == 201


def test_private_league_participant_needs_no_password(login_as, db_session, league_match):
    api = login_as(league_match.user_2)
    # el rival no está en league_participants salvo que se inscriba:
    from app.models.league_participant import LeagueParticipant
    db_session.add(LeagueParticipant(league_id=league_match.league_id, user_id=league_match.user_2_id))
    db_session.commit()
    assert api.post(f"/matches/{league_match.id}/connections").status_code == 201