import threading
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.domain.behavior import BehaviorType, BehaviorUsage
from app.domain.match import MatchStatus
from app.models.behavior import Behavior
from app.models.league import LeagueStatus
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.player import Player
from app.models.team_member import MemberRole, TeamMember
from app.repositories.behavior_abstract import UpdateBehaviorData
from app.repositories.behavior_sqlalchemy import SqlAlchemyBehaviorRepository
from app.tests.integration.match_factories import ROLES, add_league, add_team

pytestmark = pytest.mark.integration


def url(behavior_id):
    return f"/behaviors/{behavior_id}"


def add_behavior(db_session, user_id, name, behavior_type=BehaviorType.player_behavior):
    behavior = Behavior(user_id=user_id, name=name, code="x = 1", type=behavior_type)
    db_session.add(behavior)
    db_session.commit()
    return behavior


def is_deleted(db_session, behavior):
    db_session.refresh(behavior)
    return behavior.deleted


def league_team(db_session, behavior, status):
    """Liga del usuario 1 en `status`, con `behavior` en sus 6 jugadores."""
    league = add_league(db_session)
    league.status = LeagueStatus(status)
    db_session.add(LeagueParticipant(league_id=league.id, user_id=1))
    db_session.commit()
    add_team(db_session, 1, behavior, league_id=league.id)
    return league


def friendly_team(db_session, behavior, status, rival_id=None):
    """Amistoso del usuario 1 en `status`, con `behavior` en sus 6 jugadores."""
    finished = status == MatchStatus.finished
    match = Match(
        user_1_id=1,
        user_2_id=rival_id,
        status=status,
        score_1=1 if finished else None,
        score_2=0 if finished else None,
    )
    db_session.add(match)
    db_session.commit()
    add_team(db_session, 1, behavior, match_id=match.id)
    return match


# --- 401, 404 y 403 -------------------------------------------------------------


def test_without_session_is_401_and_does_not_delete(client, db_session, make_user):
    make_user(1)
    behavior = add_behavior(db_session, 1, "mio")

    response = client.delete(url(behavior.id))

    assert response.status_code == 401
    assert not is_deleted(db_session, behavior)


@pytest.mark.parametrize("behavior_id", ["999", "abc", "0"])
def test_a_missing_or_invalid_id_is_404(login, behavior_id):
    response = login(1).delete(url(behavior_id))

    assert response.status_code == 404
    assert response.json()["code"] is None


def test_an_already_deleted_behavior_is_404(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, "mio")
    assert api.delete(url(behavior.id)).status_code == 204

    response = api.delete(url(behavior.id))

    assert response.status_code == 404


def test_another_users_behavior_is_403_and_is_not_deleted(login, db_session, make_user):
    make_user(2)
    other = add_behavior(db_session, 2, "ajeno")

    response = login(1).delete(url(other.id))

    assert response.status_code == 403
    assert response.json()["code"] is None
    assert not is_deleted(db_session, other)


# --- 409: en uso ----------------------------------------------------------------


@pytest.mark.parametrize("status", ["preparation", "started"])
def test_a_player_behavior_in_an_active_league_is_in_league_team(login, db_session, status):
    api = login(1)
    behavior = add_behavior(db_session, 1, "mio")
    league_team(db_session, behavior, status)

    response = api.delete(url(behavior.id))

    assert response.status_code == 409
    assert response.json()["code"] == "behaviorInLeagueTeam"
    assert not is_deleted(db_session, behavior)


def test_the_coach_of_a_league_team_is_in_league_team(login, db_session):
    api = login(1)
    coach = add_behavior(db_session, 1, "DT", BehaviorType.coach_behavior)
    league = league_team(db_session, add_behavior(db_session, 1, "jugador"), "preparation")
    participant = db_session.get(LeagueParticipant, (league.id, 1))
    participant.coach_behavior_id = coach.id
    db_session.commit()

    response = api.delete(url(coach.id))

    assert response.status_code == 409
    assert response.json()["code"] == "behaviorInLeagueTeam"
    assert not is_deleted(db_session, coach)


@pytest.mark.parametrize(
    "status, rival_id", [(MatchStatus.scheduled, None), (MatchStatus.started, 2)]
)
def test_a_behavior_in_an_unfinished_friendly_is_in_match(
    login, db_session, make_user, status, rival_id
):
    api = login(1)
    make_user(2)
    behavior = add_behavior(db_session, 1, "mio")
    friendly_team(db_session, behavior, status, rival_id)

    response = api.delete(url(behavior.id))

    assert response.status_code == 409
    assert response.json()["code"] == "behaviorInMatch"
    assert not is_deleted(db_session, behavior)


def test_in_a_league_and_in_a_friendly_reports_the_league(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, "mio")
    league_team(db_session, behavior, "started")
    friendly_team(db_session, behavior, MatchStatus.scheduled)

    response = api.delete(url(behavior.id))

    assert response.json()["code"] == "behaviorInLeagueTeam"


# --- 204 ------------------------------------------------------------------------


def test_an_unused_behavior_is_deleted_and_disappears(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, "mio")
    kept = add_behavior(db_session, 1, "otro")

    response = api.delete(url(behavior.id))

    assert response.status_code == 204
    assert response.content == b""
    assert is_deleted(db_session, behavior)  # borrado lógico: la fila sigue
    assert [item["id"] for item in api.get("/behaviors/me").json()["items"]] == [kept.id]
    assert api.get(url(behavior.id)).status_code == 404


@pytest.mark.parametrize("status", ["cancelled", "finished"])
def test_a_behavior_only_in_an_ended_league_can_be_deleted(login, db_session, make_user, status):
    api = login(1)
    make_user(2)
    behavior = add_behavior(db_session, 1, "mio")
    league = league_team(db_session, behavior, status)
    match = Match(
        league_id=league.id,
        user_1_id=1,
        user_2_id=2,
        status=MatchStatus.finished,
        scheduled_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        score_1=2,
        score_2=1,
    )
    db_session.add(match)
    db_session.commit()

    response = api.delete(url(behavior.id))

    assert response.status_code == 204
    assert api.get(f"/matches/{match.id}").status_code == 200


@pytest.mark.parametrize("status", [MatchStatus.finished, MatchStatus.cancelled])
def test_a_behavior_only_in_an_ended_friendly_can_be_deleted(login, db_session, make_user, status):
    api = login(1)
    make_user(2)
    behavior = add_behavior(db_session, 1, "mio")
    rival_id = 2 if status == MatchStatus.finished else None
    match = friendly_team(db_session, behavior, status, rival_id)

    response = api.delete(url(behavior.id))

    assert response.status_code == 204
    assert api.get(f"/matches/{match.id}").status_code == 200


# --- Después de eliminarlo ------------------------------------------------------


def test_its_name_can_be_used_again(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, "mio")
    api.delete(url(behavior.id))

    response = api.post("/behaviors", json={"name": "mio", "code": "", "type": "playerBehavior"})

    assert response.status_code == 201


def test_a_new_team_with_it_is_not_owned(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, "mio")
    api.delete(url(behavior.id))
    players = [
        Player(user_id=1, name=f"J{i}", power=60, agility=60, control=60, strength=60, speed=60)
        for i in range(6)
    ]
    db_session.add_all(players)
    db_session.commit()
    members = [
        {"playerId": player.id, "role": role.value, "behaviorId": behavior.id}
        for player, role in zip(players, ROLES)
    ]

    response = api.post("/friendlies", json={"name": "Amistoso", "members": members})

    assert response.status_code == 409
    assert response.json()["code"] == "playerOrBehaviorNotOwned"


def test_editing_it_is_deleted_concurrently(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, "mio")
    api.delete(url(behavior.id))

    response = api.put(url(behavior.id), json={"name": "mio", "code": ""})

    assert response.status_code == 404
    assert response.json()["code"] == "deletedConcurrently"


def test_a_behavior_deleted_after_reading_it_is_not_updated(login, db_session):
    api = login(1)
    behavior = add_behavior(db_session, 1, "mio")
    api.delete(url(behavior.id))

    result = SqlAlchemyBehaviorRepository(db_session).update(
        behavior.id, UpdateBehaviorData(name="nuevo", code="")
    )

    assert result is None
    db_session.refresh(behavior)
    assert behavior.name == "mio"


# --- Atomicidad -----------------------------------------------------------------


def test_the_delete_waits_for_a_team_being_saved_and_sees_it(db_session, make_user):
    """Un request arma un amistoso con el behavior; mientras no confirma, el
    DELETE espera, y cuando confirma, el DELETE ve el equipo y no lo elimina."""
    make_user(1)
    behavior = add_behavior(db_session, 1, "mio")
    match = Match(user_1_id=1, status=MatchStatus.scheduled)
    player = Player(user_id=1, name="J", power=60, agility=60, control=60, strength=60, speed=60)
    db_session.add_all([match, player])
    db_session.commit()
    engine = db_session.get_bind()
    result = {}

    def delete():
        with Session(engine) as deleting:
            result["usage"] = SqlAlchemyBehaviorRepository(deleting).delete_if_unused(behavior.id)

    with Session(engine) as saving:
        assert SqlAlchemyBehaviorRepository(saving).owned_behavior_ids(1, [behavior.id])
        deleter = threading.Thread(target=delete)
        deleter.start()
        deleter.join(timeout=0.5)
        assert deleter.is_alive()  # espera al equipo que se está guardando
        saving.add(
            TeamMember(
                match_id=match.id,
                user_id=1,
                player_id=player.id,
                behavior_id=behavior.id,
                role=MemberRole.forward,
            )
        )
        saving.commit()
    deleter.join(timeout=5)

    assert result["usage"] == BehaviorUsage.match
    assert not is_deleted(db_session, behavior)
