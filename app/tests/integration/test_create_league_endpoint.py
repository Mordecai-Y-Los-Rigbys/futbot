import pytest
from sqlalchemy import func, select

from app.models.behavior import Behavior
from app.models.league import League, LeagueStatus
from app.models.league_participant import LeagueParticipant
from app.models.team_member import TeamMember
from app.models.player import Player

pytestmark = pytest.mark.integration

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


@pytest.fixture()
def team_of(db_session):
    """Crea 6 jugadores y un behavior del usuario; devuelve el `members` listo."""

    def _make(user):
        players = [
            Player(
                user_id=user.id,
                name=f"p{i}",
                power=60,
                agility=60,
                control=60,
                strength=60,
                speed=60,
            )
            for i in range(6)
        ]
        behavior = Behavior(user_id=user.id, name="b", code="...")
        db_session.add_all([*players, behavior])
        db_session.commit()
        return [
            {"playerId": p.id, "behaviorId": behavior.id, "role": r} for p, r in zip(players, ROLES)
        ]

    return _make


def body_for(members, **over):
    base = {
        "name": "Nueva",
        "minParticipants": 3,
        "maxParticipants": 8,
        "matchDuration": 5,
        "private": False,
        "members": members,
    }
    base.update(over)
    return base


def count(db_session, model):
    return db_session.scalar(select(func.count()).select_from(model))


def test_create_league_enrolls_creator_with_team(login_as, create_user, team_of, db_session):
    creator = create_user("creator")
    api = login_as(creator)

    resp = api.post(
        "/leagues",
        json=body_for(team_of(creator), private=True, password="secret"),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["participantsCount"] == 1
    assert body["private"] is True
    assert body["creator"]["id"] == creator.id

    league = db_session.get(League, body["id"])
    assert league.status == LeagueStatus.preparation
    assert league.password == "secret"  # se guarda tal cual, sin hashear
    assert count(db_session, LeagueParticipant) == 1
    assert count(db_session, TeamMember) == 6
    assert api.get("/leagues").json()["total"] == 1  # visible en el listado


def test_public_league_does_not_persist_password(login_as, create_user, team_of, db_session):
    creator = create_user("creator")
    api = login_as(creator)

    resp = api.post("/leagues", json=body_for(team_of(creator), password="ignorada"))

    assert resp.status_code == 201
    assert db_session.get(League, resp.json()["id"]).password is None


def test_nothing_is_persisted_when_team_is_not_owned(login_as, create_user, team_of, db_session):
    other, creator = create_user("other"), create_user("creator")

    resp = login_as(creator).post("/leagues", json=body_for(team_of(other)))  # equipo ajeno

    assert resp.status_code == 409
    assert resp.json()["code"] == "playerOrBehaviorNotOwned"
    assert count(db_session, League) == 0
    assert count(db_session, LeagueParticipant) == 0
    assert count(db_session, TeamMember) == 0


def test_invalid_payload_persists_nothing(login_as, create_user, team_of, db_session):
    creator = create_user("creator")

    resp = login_as(creator).post("/leagues", json=body_for(team_of(creator), minParticipants=2))

    assert resp.status_code == 400
    assert resp.json()["code"] == "minParticipantsTooLow"
    assert count(db_session, League) == 0
