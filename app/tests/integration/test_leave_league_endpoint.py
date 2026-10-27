import pytest
from sqlalchemy import func, select

from app.domain.team_member import MemberRole
from app.models.behavior import Behavior
from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.models.player import Player
from app.models.team_member import TeamMember

pytestmark = pytest.mark.integration

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


@pytest.fixture()
def join_with_team(db_session, add_participant):
    """Inscribe al usuario en la liga y le registra un equipo de 6."""

    def _join(league, user):
        add_participant(league, user)  # el participante debe existir antes (FK)
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
        db_session.add_all(
            TeamMember(
                league_id=league.id,
                match_id=None,
                user_id=user.id,
                player_id=p.id,
                behavior_id=behavior.id,
                role=MemberRole(r),
            )
            for p, r in zip(players, ROLES)
        )
        db_session.commit()

    return _join


def count(db_session, model, **filters):
    stmt = select(func.count()).select_from(model)
    for field, value in filters.items():
        stmt = stmt.where(getattr(model, field) == value)
    return db_session.scalar(stmt)


def snapshot(db_session):
    """Cantidad total de inscripciones y de integrantes de equipo."""
    return count(db_session, LeagueParticipant), count(db_session, TeamMember)


# --- caso exitoso -------------------------------------------------------------


def test_leave_removes_participation_and_team(
    login_as, create_user, make_league, join_with_team, db_session
):
    creator, member = create_user("creator"), create_user("member")
    league = make_league(creator)
    join_with_team(league, member)

    resp = login_as(member).delete(f"/leagues/{league.id}/participants/me")

    assert resp.status_code == 204
    assert resp.content == b""
    assert count(db_session, LeagueParticipant, league_id=league.id, user_id=member.id) == 0
    assert count(db_session, TeamMember, league_id=league.id, user_id=member.id) == 0


def test_leave_does_not_touch_creator_nor_other_participants(
    login_as, create_user, make_league, join_with_team, db_session
):
    creator, member, other = create_user("creator"), create_user("member"), create_user("other")
    league = make_league(creator)
    join_with_team(league, member)
    join_with_team(league, other)

    resp = login_as(member).delete(f"/leagues/{league.id}/participants/me")

    assert resp.status_code == 204
    assert count(db_session, LeagueParticipant, league_id=league.id) == 2  # creador + other
    assert count(db_session, LeagueParticipant, league_id=league.id, user_id=creator.id) == 1
    assert count(db_session, LeagueParticipant, league_id=league.id, user_id=other.id) == 1
    assert count(db_session, TeamMember, league_id=league.id, user_id=other.id) == 6
    assert db_session.get(League, league.id) is not None  # la liga sigue existiendo


def test_leave_keeps_membership_in_other_leagues(
    login_as, create_user, make_league, join_with_team, db_session
):
    creator, member = create_user("creator"), create_user("member")
    league_a, league_b = make_league(creator, name="A"), make_league(creator, name="B")
    join_with_team(league_a, member)
    join_with_team(league_b, member)

    resp = login_as(member).delete(f"/leagues/{league_a.id}/participants/me")

    assert resp.status_code == 204
    assert count(db_session, LeagueParticipant, league_id=league_b.id, user_id=member.id) == 1
    assert count(db_session, TeamMember, league_id=league_b.id, user_id=member.id) == 6


def test_leave_frees_the_slot(login_as, create_user, make_league, join_with_team):
    creator, member = create_user("creator"), create_user("member")
    league = make_league(creator)
    join_with_team(league, member)
    api = login_as(member)
    assert api.get("/leagues").json()["items"][0]["participantsCount"] == 2

    assert api.delete(f"/leagues/{league.id}/participants/me").status_code == 204

    assert api.get("/leagues").json()["items"][0]["participantsCount"] == 1


def test_leave_twice_second_is_not_participating(
    login_as, create_user, make_league, join_with_team
):
    creator, member = create_user("creator"), create_user("member")
    league = make_league(creator)
    join_with_team(league, member)
    api = login_as(member)

    assert api.delete(f"/leagues/{league.id}/participants/me").status_code == 204
    resp = api.delete(f"/leagues/{league.id}/participants/me")

    assert resp.status_code == 409
    assert resp.json()["code"] == "notParticipating"


# --- fallos: no se elimina nada -----------------------------------------------


def test_creator_cannot_leave(login_as, create_user, make_league, join_with_team, db_session):
    creator = create_user("creator")
    league = make_league(creator)
    join_with_team(league, create_user("member"))
    before = snapshot(db_session)

    resp = login_as(creator).delete(f"/leagues/{league.id}/participants/me")

    assert resp.status_code == 409
    assert resp.json()["code"] == "isCreator"
    assert snapshot(db_session) == before


def test_non_participant_cannot_leave(login_as, create_user, make_league, db_session):
    creator, stranger = create_user("creator"), create_user("stranger")
    league = make_league(creator)
    before = snapshot(db_session)

    resp = login_as(stranger).delete(f"/leagues/{league.id}/participants/me")

    assert resp.status_code == 409
    assert resp.json()["code"] == "notParticipating"
    assert snapshot(db_session) == before


@pytest.mark.parametrize("status", ["started", "finished", "cancelled"])
def test_cannot_leave_if_not_in_preparation(
    login_as, create_user, make_league, join_with_team, db_session, status
):
    creator, member = create_user("creator"), create_user("member")
    league = make_league(creator, status=status)
    join_with_team(league, member)
    before = snapshot(db_session)

    resp = login_as(member).delete(f"/leagues/{league.id}/participants/me")

    assert resp.status_code == 409
    assert resp.json()["code"] == "notInPreparation"
    assert snapshot(db_session) == before


def test_nonexistent_league_is_404(login_as, create_user):
    resp = login_as(create_user("member")).delete("/leagues/999/participants/me")
    assert resp.status_code == 404
    assert resp.json()["code"] is None


@pytest.mark.parametrize("raw", ["abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_id_is_404_never_400_or_422(login_as, create_user, raw):
    resp = login_as(create_user("member")).delete(f"/leagues/{raw}/participants/me")
    assert resp.status_code == 404
    assert resp.json()["code"] is None


def test_no_session_is_401(client, create_user, make_league):
    league = make_league(create_user("creator"))
    resp = client.delete(f"/leagues/{league.id}/participants/me")
    assert resp.status_code == 401
    assert resp.json()["code"] is None


def test_401_goes_before_404(client):
    assert client.delete("/leagues/999/participants/me").status_code == 401


def test_404_goes_before_409(login_as, create_user):
    # Liga inexistente + usuario que no participa: gana el 404
    resp = login_as(create_user("stranger")).delete("/leagues/999/participants/me")
    assert resp.status_code == 404