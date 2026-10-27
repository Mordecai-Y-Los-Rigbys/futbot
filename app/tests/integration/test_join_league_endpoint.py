"""POST /leagues/{id}/participants contra la base real (Postgres)."""

import threading
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.domain.behavior import BehaviorType
from app.main import app
from app.models.behavior import Behavior
from app.models.league import League, LeagueStatus
from app.models.league_participant import LeagueParticipant
from app.models.player import Player
from app.models.session_league_unlock import SessionLeagueUnlock
from app.models.team_member import TeamMember
from app.repositories.league_abstract import CreateLeagueMemberData, JoinLeagueData
from app.repositories.league_sqlalchemy import SqlAlchemyLeagueRepository
from app.schemas.errors import Error, JoinLeagueConflict, JoinLeagueForbidden, ValidationBadRequest
from app.api.deps import get_league_service
from app.repositories.behavior_sqlalchemy import SqlAlchemyBehaviorRepository
from app.repositories.player_sqlalchemy import SqlAlchemyPlayerRepository
from app.services.league_service import LeagueService

pytestmark = pytest.mark.integration

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]
PASSWORD = "secret"  # la que usa make_league para las ligas privadas


# --- fakes y fixtures ---------------------------------------------------------


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def participants_changed(self, league_id):
        self.calls.append(league_id)


@pytest.fixture(autouse=True)
def notifier(db_session):
    """Servicio real con los repositorios de la base y un notificador fake."""
    fake = FakeNotifier()
    app.dependency_overrides[get_league_service] = lambda: LeagueService(
        SqlAlchemyLeagueRepository(db_session),
        SqlAlchemyPlayerRepository(db_session),
        SqlAlchemyBehaviorRepository(db_session),
        notifier=fake,
    )
    yield fake
    app.dependency_overrides.pop(get_league_service, None)


@pytest.fixture()
def creator(create_user):
    return create_user("creator", "Creator FC")


@pytest.fixture()
def joiner(create_user):
    return create_user("joiner", "Joiner FC")


@pytest.fixture()
def other(create_user):
    return create_user("other")


def add_behavior(db_session, user, name, kind=BehaviorType.player_behavior) -> Behavior:
    behavior = Behavior(user_id=user.id, name=name, code="def behave(): pass", type=kind)
    db_session.add(behavior)
    db_session.commit()
    return behavior


@pytest.fixture()
def make_team(db_session):
    """make_team(user) -> (members listos para enviar, id del behavior de DT)."""

    def _make(user):
        players = [
            Player(
                user_id=user.id,
                name=f"J{i}",
                power=60,
                agility=60,
                control=60,
                strength=60,
                speed=60,
            )
            for i in range(6)
        ]
        db_session.add_all(players)
        db_session.commit()
        behaviors = [add_behavior(db_session, user, f"b{user.id}_{i}") for i in range(6)]
        coach = add_behavior(db_session, user, f"dt{user.id}", BehaviorType.coach_behavior)
        members = [
            {"playerId": p.id, "role": r, "behaviorId": b.id}
            for p, r, b in zip(players, ROLES, behaviors)
        ]
        return members, coach.id

    return _make


@pytest.fixture()
def joiner_team(joiner, make_team):
    return make_team(joiner)


@pytest.fixture()
def team_body(joiner_team):
    members, coach_id = joiner_team
    return {"members": members, "coachBehaviorId": coach_id}


@pytest.fixture()
def public_league(creator, make_league):
    return make_league(creator, "Publica")


@pytest.fixture()
def private_league(creator, make_league):
    return make_league(creator, "Privada", private=True)


def url(league_id):
    return f"/leagues/{league_id}/participants"


def participant(db_session, league_id, user_id) -> LeagueParticipant | None:
    db_session.expire_all()
    return db_session.get(LeagueParticipant, (league_id, user_id))


def participants_count(db_session, league_id) -> int:
    db_session.expire_all()
    return db_session.scalar(
        select(func.count())
        .select_from(LeagueParticipant)
        .where(LeagueParticipant.league_id == league_id)
    )


def team_of(db_session, league_id, user_id):
    db_session.expire_all()
    rows = db_session.scalars(
        select(TeamMember).where(TeamMember.league_id == league_id, TeamMember.user_id == user_id)
    ).all()
    return sorted((m.player_id, m.behavior_id, m.role.value) for m in rows)


def expected_team(members):
    return sorted((m["playerId"], m["behaviorId"], m["role"]) for m in members)


def is_unlocked(db_session, session_id, league_id) -> bool:
    db_session.expire_all()
    return db_session.get(SessionLeagueUnlock, (session_id, league_id)) is not None


def session_of(api) -> str:
    return api.cookies.get("session_id")


def assert_not_joined(db_session, league, user, notifier, count=1):
    assert participant(db_session, league.id, user.id) is None
    assert team_of(db_session, league.id, user.id) == []
    assert participants_count(db_session, league.id) == count
    assert notifier.calls == []


def codes(resp):
    return [(e["field"], e["reason"]) for e in resp.json()["errors"]]


# --- inscripción exitosa ------------------------------------------------------


def test_join_public_league_persists_team_and_coach(
    login_as, db_session, public_league, joiner, joiner_team, team_body, notifier
):
    members, coach_id = joiner_team
    assert participants_count(db_session, public_league.id) == 1  # solo el creador

    resp = login_as(joiner).post(url(public_league.id), json=team_body)

    assert resp.status_code == 201, resp.text
    assert resp.content == b""
    row = participant(db_session, public_league.id, joiner.id)
    assert row is not None and row.coach_behavior_id == coach_id
    assert team_of(db_session, public_league.id, joiner.id) == expected_team(members)
    assert participants_count(db_session, public_league.id) == 2
    assert notifier.calls == [public_league.id]


def test_join_public_league_does_not_unlock_the_session(
    login_as, db_session, public_league, joiner, team_body
):
    api = login_as(joiner)
    assert api.post(url(public_league.id), json=team_body).status_code == 201
    assert not is_unlocked(db_session, session_of(api), public_league.id)


@pytest.mark.parametrize("password", [123, None, "", "cualquiera", ["x"]])
def test_public_league_ignores_password_of_any_type(
    login_as, db_session, public_league, joiner, team_body, password
):
    resp = login_as(joiner).post(url(public_league.id), json={**team_body, "password": password})
    assert resp.status_code == 201, resp.text
    assert participant(db_session, public_league.id, joiner.id) is not None


def test_join_private_league_persists_and_unlocks_the_session(
    login_as, db_session, private_league, joiner, joiner_team, team_body, notifier
):
    members, coach_id = joiner_team
    api = login_as(joiner)
    other_session = login_as(joiner)  # otra sesión del mismo usuario

    resp = api.post(url(private_league.id), json={**team_body, "password": PASSWORD})

    assert resp.status_code == 201, resp.text
    assert participant(db_session, private_league.id, joiner.id).coach_behavior_id == coach_id
    assert team_of(db_session, private_league.id, joiner.id) == expected_team(members)
    assert participants_count(db_session, private_league.id) == 2
    assert is_unlocked(db_session, session_of(api), private_league.id)
    # el desbloqueo es por sesión: la otra sesión no queda desbloqueada
    assert not is_unlocked(db_session, session_of(other_session), private_league.id)
    assert notifier.calls == [private_league.id]


@pytest.mark.parametrize("extra", [{}, {"coachBehaviorId": None}])
def test_join_without_coach(login_as, db_session, public_league, joiner, joiner_team, extra):
    members, _ = joiner_team
    resp = login_as(joiner).post(url(public_league.id), json={"members": members, **extra})
    assert resp.status_code == 201, resp.text
    assert participant(db_session, public_league.id, joiner.id).coach_behavior_id is None
    assert team_of(db_session, public_league.id, joiner.id) == expected_team(members)


def test_same_player_behavior_for_all_members(
    login_as, db_session, public_league, joiner, joiner_team
):
    members, coach_id = joiner_team
    shared = members[0]["behaviorId"]
    same = [{**m, "behaviorId": shared} for m in members]
    resp = login_as(joiner).post(
        url(public_league.id), json={"members": same, "coachBehaviorId": coach_id}
    )
    assert resp.status_code == 201, resp.text
    assert {b for _, b, _ in team_of(db_session, public_league.id, joiner.id)} == {shared}


def test_players_can_be_in_teams_of_different_leagues(
    login_as, db_session, creator, make_league, joiner, team_body
):
    first, second = make_league(creator, "Una"), make_league(creator, "Otra")
    api = login_as(joiner)
    assert api.post(url(first.id), json=team_body).status_code == 201
    assert api.post(url(second.id), json=team_body).status_code == 201


def test_last_free_spot_can_be_taken(login_as, db_session, creator, make_league, joiner, team_body):
    league = make_league(creator, "Chica", max_participants=2)
    assert login_as(joiner).post(url(league.id), json=team_body).status_code == 201
    assert participants_count(db_session, league.id) == 2


# --- 401 ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, payload",
    [
        ("/leagues/1/participants", {}),
        ("/leagues/abc/participants", {"members": 5}),
        ("/leagues/0/participants", None),
    ],
)
def test_no_cookie_is_401_even_with_bad_id_or_body(client, notifier, path, payload):
    resp = client.post(path, json=payload)
    assert resp.status_code == 401 and resp.json()["code"] is None
    Error.model_validate(resp.json())
    assert notifier.calls == []


def test_nonexistent_session_is_401(client, public_league):
    client.cookies.set("session_id", "no-existe")
    assert client.post(url(public_league.id), json={}).status_code == 401


def test_expired_session_is_401(login_as, public_league, joiner, team_body):
    expired = login_as(joiner, expires_in=timedelta(days=-1))
    resp = expired.post(url(public_league.id), json=team_body)
    assert resp.status_code == 401 and resp.json()["code"] is None


# --- 404 ----------------------------------------------------------------------


@pytest.mark.parametrize("raw_id", ["abc", "1.5", "0", "-1", "2147483648", "99999999999999999999"])
def test_invalid_route_id_is_404_never_400_or_422(login_as, joiner, team_body, raw_id):
    api = login_as(joiner)
    for kwargs in ({"json": team_body}, {"json": {"members": 5}}, {}):
        resp = api.post(f"/leagues/{raw_id}/participants", **kwargs)
        assert resp.status_code == 404 and resp.json()["code"] is None


def test_nonexistent_league_is_404(login_as, joiner, team_body, notifier):
    resp = login_as(joiner).post(url(2147483647), json=team_body)
    assert resp.status_code == 404
    assert resp.json() == {"code": None, "message": "La liga no existe."}
    assert notifier.calls == []


# --- 400 ----------------------------------------------------------------------


def test_missing_members_is_required(login_as, db_session, public_league, joiner, notifier):
    resp = login_as(joiner).post(url(public_league.id), json={"coachBehaviorId": 1})
    assert resp.status_code == 400
    ValidationBadRequest.model_validate(resp.json())
    assert resp.json()["code"] == "invalidFields"
    assert codes(resp) == [("members", "required")]
    assert_not_joined(db_session, public_league, joiner, notifier)


@pytest.mark.parametrize(
    "password, reason", [(None, "required"), ("__missing__", "required"), (123, "invalidType")]
)
def test_private_password_validation(
    login_as, db_session, private_league, joiner, team_body, notifier, password, reason
):
    payload = dict(team_body)
    if password != "__missing__":
        payload["password"] = password
    resp = login_as(joiner).post(url(private_league.id), json=payload)
    assert resp.status_code == 400
    assert codes(resp) == [("password", reason)]
    assert_not_joined(db_session, private_league, joiner, notifier)


def test_invalid_team_is_reported_on_members(
    login_as, db_session, public_league, joiner, joiner_team, notifier
):
    members, coach_id = joiner_team
    two_forwards = [dict(m) for m in members]
    two_forwards[1]["role"] = "forward"
    resp = login_as(joiner).post(
        url(public_league.id), json={"members": two_forwards, "coachBehaviorId": coach_id}
    )
    assert resp.status_code == 400
    assert codes(resp) == [("members", "invalidTeam")]
    assert_not_joined(db_session, public_league, joiner, notifier)


def test_bad_ids_in_the_body_are_400_not_404_or_409(
    login_as, db_session, public_league, joiner, joiner_team, notifier
):
    members, _ = joiner_team
    bad = [dict(m) for m in members]
    bad[0]["playerId"] = "abc"
    bad[1]["behaviorId"] = 2147483648
    resp = login_as(joiner).post(url(public_league.id), json={"members": bad, "coachBehaviorId": 0})
    assert resp.status_code == 400
    assert codes(resp) == [
        ("members[0].playerId", "invalidType"),
        ("members[1].behaviorId", "outOfRange"),
        ("coachBehaviorId", "outOfRange"),
    ]
    assert_not_joined(db_session, public_league, joiner, notifier)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"content": "{", "headers": {"Content-Type": "application/json"}},
        {"json": []},
        {"json": "x"},
    ],
)
def test_unreadable_body(
    login_as, db_session, public_league, private_league, joiner, notifier, kwargs
):
    api = login_as(joiner)
    resp = api.post(url(public_league.id), **kwargs)
    assert resp.status_code == 400 and codes(resp) == [("members", "required")]
    resp = api.post(url(private_league.id), **kwargs)
    assert resp.status_code == 400
    assert codes(resp) == [("password", "required"), ("members", "required")]
    assert notifier.calls == []


# --- 403 ----------------------------------------------------------------------


@pytest.mark.parametrize("password", ["", "wrong", "SECRET"])
def test_wrong_or_empty_password_is_403(
    login_as, db_session, private_league, joiner, team_body, notifier, password
):
    api = login_as(joiner)
    resp = api.post(url(private_league.id), json={**team_body, "password": password})
    assert resp.status_code == 403
    JoinLeagueForbidden.model_validate(resp.json())
    assert resp.json()["code"] == "invalidLeaguePassword"
    assert_not_joined(db_session, private_league, joiner, notifier)
    assert not is_unlocked(db_session, session_of(api), private_league.id)


def test_wrong_password_is_403_even_if_the_session_already_unlocked_the_league(
    login_as, db_session, private_league, joiner, team_body, notifier
):
    api = login_as(joiner)
    db_session.add(SessionLeagueUnlock(session_id=session_of(api), league_id=private_league.id))
    db_session.commit()

    resp = api.post(url(private_league.id), json={**team_body, "password": "wrong"})
    assert resp.status_code == 403
    assert_not_joined(db_session, private_league, joiner, notifier)

    # con la contraseña correcta se inscribe y el desbloqueo previo no estorba
    resp = api.post(url(private_league.id), json={**team_body, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    assert is_unlocked(db_session, session_of(api), private_league.id)


# --- 409 ----------------------------------------------------------------------


def set_status(db_session, league, status):
    league.status = LeagueStatus(status)
    db_session.commit()


@pytest.mark.parametrize("status", ["started", "finished", "cancelled"])
def test_league_not_in_preparation(
    login_as, db_session, public_league, joiner, team_body, notifier, status
):
    set_status(db_session, public_league, status)
    resp = login_as(joiner).post(url(public_league.id), json=team_body)
    assert resp.status_code == 409
    JoinLeagueConflict.model_validate(resp.json())
    assert resp.json()["code"] == "notInPreparation"
    assert_not_joined(db_session, public_league, joiner, notifier)


def test_league_full(
    login_as,
    db_session,
    creator,
    make_league,
    add_participant,
    other,
    joiner,
    team_body,
    notifier,
):
    league = make_league(creator, "Llena", max_participants=2)
    add_participant(league, other)
    resp = login_as(joiner).post(url(league.id), json=team_body)
    assert resp.status_code == 409 and resp.json()["code"] == "leagueFull"
    assert_not_joined(db_session, league, joiner, notifier, count=2)


def test_already_participating(
    login_as, db_session, public_league, joiner, joiner_team, team_body, notifier
):
    members, _ = joiner_team
    api = login_as(joiner)
    assert api.post(url(public_league.id), json=team_body).status_code == 201
    notifier.calls.clear()

    resp = api.post(url(public_league.id), json=team_body)
    assert resp.status_code == 409 and resp.json()["code"] == "alreadyParticipating"
    assert participants_count(db_session, public_league.id) == 2
    assert team_of(db_session, public_league.id, joiner.id) == expected_team(
        members
    )  # sin duplicar
    assert notifier.calls == []


def test_creator_already_participates(login_as, db_session, public_league, creator, make_team):
    members, coach_id = make_team(creator)
    resp = login_as(creator).post(
        url(public_league.id), json={"members": members, "coachBehaviorId": coach_id}
    )
    assert resp.status_code == 409 and resp.json()["code"] == "alreadyParticipating"


def foreign(db_session, user, kind=BehaviorType.player_behavior):
    """Ids de un jugador y un behavior de otro usuario."""
    player = Player(
        user_id=user.id, name="Ajeno", power=60, agility=60, control=60, strength=60, speed=60
    )
    db_session.add(player)
    db_session.commit()
    return player.id, add_behavior(db_session, user, f"ajeno-{kind.value}", kind).id


@pytest.mark.parametrize("target", ["player", "member_behavior", "coach"])
def test_foreign_ids_are_not_owned(
    login_as, db_session, public_league, joiner, other, joiner_team, notifier, target
):
    members, coach_id = joiner_team
    members = [dict(m) for m in members]
    foreign_player, foreign_player_behavior = foreign(db_session, other)
    _, foreign_coach = foreign(db_session, other, BehaviorType.coach_behavior)
    if target == "player":
        members[0]["playerId"] = foreign_player
    elif target == "member_behavior":
        members[0]["behaviorId"] = foreign_player_behavior
    else:
        coach_id = foreign_coach

    resp = login_as(joiner).post(
        url(public_league.id), json={"members": members, "coachBehaviorId": coach_id}
    )
    assert resp.status_code == 409 and resp.json()["code"] == "playerOrBehaviorNotOwned"
    assert_not_joined(db_session, public_league, joiner, notifier)


@pytest.mark.parametrize("target", ["player", "member_behavior", "coach"])
def test_nonexistent_ids_are_not_owned(
    login_as, db_session, public_league, joiner, joiner_team, notifier, target
):
    members, coach_id = joiner_team
    members = [dict(m) for m in members]
    if target == "player":
        members[0]["playerId"] = 2147483647
    elif target == "member_behavior":
        members[0]["behaviorId"] = 2147483647
    else:
        coach_id = 2147483647

    resp = login_as(joiner).post(
        url(public_league.id), json={"members": members, "coachBehaviorId": coach_id}
    )
    assert resp.status_code == 409 and resp.json()["code"] == "playerOrBehaviorNotOwned"
    assert_not_joined(db_session, public_league, joiner, notifier)


def test_member_with_a_coach_behavior_is_a_type_mismatch(
    login_as, db_session, public_league, joiner, joiner_team, notifier
):
    members, coach_id = joiner_team
    members = [dict(m) for m in members]
    members[2]["behaviorId"] = coach_id  # behavior propio, pero de DT
    resp = login_as(joiner).post(
        url(public_league.id), json={"members": members, "coachBehaviorId": coach_id}
    )
    assert resp.status_code == 409 and resp.json()["code"] == "behaviorTypeMismatch"
    assert_not_joined(db_session, public_league, joiner, notifier)


def test_coach_with_a_player_behavior_is_a_type_mismatch(
    login_as, db_session, public_league, joiner, joiner_team, notifier
):
    members, _ = joiner_team
    resp = login_as(joiner).post(
        url(public_league.id),
        json={"members": members, "coachBehaviorId": members[0]["behaviorId"]},
    )
    assert resp.status_code == 409 and resp.json()["code"] == "behaviorTypeMismatch"
    assert_not_joined(db_session, public_league, joiner, notifier)


# --- varias fallas a la vez: 401 > 404 > 400 > 403 > 409 ----------------------


def test_401_beats_everything(client, private_league):
    resp = client.post("/leagues/abc/participants", json={"members": 5, "password": "wrong"})
    assert resp.status_code == 401


def test_404_beats_400(login_as, joiner):
    resp = login_as(joiner).post(url(2147483647), json={"members": "x"})
    assert resp.status_code == 404


def test_400_beats_403(login_as, db_session, private_league, joiner, joiner_team, notifier):
    members, _ = joiner_team
    resp = login_as(joiner).post(
        url(private_league.id), json={"members": members[:5], "password": "wrong"}
    )
    assert resp.status_code == 400 and codes(resp) == [("members", "invalidTeam")]
    assert_not_joined(db_session, private_league, joiner, notifier)


def test_400_beats_409(login_as, db_session, public_league, joiner, notifier):
    set_status(db_session, public_league, "started")
    resp = login_as(joiner).post(url(public_league.id), json={"members": []})
    assert resp.status_code == 400 and codes(resp) == [("members", "invalidTeam")]


def test_403_beats_409(
    login_as,
    db_session,
    creator,
    make_league,
    add_participant,
    other,
    joiner,
    joiner_team,
    notifier,
):
    league = make_league(creator, "Privada llena", max_participants=2, private=True)
    add_participant(league, other)
    set_status(db_session, league, "started")
    members, _ = joiner_team
    resp = login_as(joiner).post(
        url(league.id),
        json={"members": members, "coachBehaviorId": 2147483647, "password": "wrong"},
    )
    assert resp.status_code == 403 and resp.json()["code"] == "invalidLeaguePassword"


def test_409_order_state_before_ownership(
    login_as, db_session, public_league, joiner, joiner_team, other
):
    members, _ = joiner_team
    _, foreign_coach = foreign(db_session, other, BehaviorType.coach_behavior)
    set_status(db_session, public_league, "cancelled")
    resp = login_as(joiner).post(
        url(public_league.id), json={"members": members, "coachBehaviorId": foreign_coach}
    )
    assert resp.json()["code"] == "notInPreparation"


def test_409_ownership_beats_type_mismatch(
    login_as, db_session, public_league, joiner, joiner_team, other
):
    members, coach_id = joiner_team
    members = [dict(m) for m in members]
    members[0]["behaviorId"] = coach_id  # tipo equivocado...
    _, foreign_coach = foreign(db_session, other, BehaviorType.coach_behavior)  # ...y DT ajeno
    resp = login_as(joiner).post(
        url(public_league.id), json={"members": members, "coachBehaviorId": foreign_coach}
    )
    assert resp.json()["code"] == "playerOrBehaviorNotOwned"


# --- repositorio: atomicidad y concurrencia -----------------------------------


def join_data(league_id, user_id, session_id, members, coach_id, unlock=False):
    return JoinLeagueData(
        league_id=league_id,
        user_id=user_id,
        session_id=session_id,
        members=[
            CreateLeagueMemberData(
                player_id=m["playerId"], behavior_id=m["behaviorId"], role=m["role"]
            )
            for m in members
        ],
        coach_behavior_id=coach_id,
        unlock_session=unlock,
    )


def test_failure_while_saving_the_team_rolls_back_everything(
    login_as, db_session, private_league, joiner, joiner_team
):
    from sqlalchemy.exc import IntegrityError

    members, coach_id = joiner_team
    api = login_as(joiner)
    bad = [{**m, "playerId": 2147483000 + i} for i, m in enumerate(members)]  # FK inexistente
    repo = SqlAlchemyLeagueRepository(db_session)
    with pytest.raises(IntegrityError):
        repo.join(join_data(private_league.id, joiner.id, session_of(api), bad, coach_id, True))

    assert participant(db_session, private_league.id, joiner.id) is None
    assert not is_unlocked(db_session, session_of(api), private_league.id)
    # la liga sigue admitiendo al usuario
    assert (
        repo.join(join_data(private_league.id, joiner.id, session_of(api), members, coach_id, True))
        is None
    )


def test_repo_rechecks_state_when_writing(db_session, public_league, joiner, joiner_team):
    members, coach_id = joiner_team
    repo = SqlAlchemyLeagueRepository(db_session)
    assert repo.get_join_state(public_league.id, joiner.id).conflict() is None
    set_status(db_session, public_league, "started")  # cambió entre la lectura y la escritura
    assert repo.join(join_data(public_league.id, joiner.id, "s", members, coach_id)) == (
        "notInPreparation"
    )
    assert participant(db_session, public_league.id, joiner.id) is None


def test_repo_get_join_state(db_session, private_league, creator, joiner):
    repo = SqlAlchemyLeagueRepository(db_session)
    st = repo.get_join_state(private_league.id, joiner.id)
    assert (st.private, st.password, st.status) == (True, PASSWORD, LeagueStatus.preparation)
    assert (st.participants_count, st.max_participants, st.is_participant) == (1, 8, False)
    assert repo.get_join_state(private_league.id, creator.id).is_participant is True
    assert repo.get_join_state(2147483647, joiner.id) is None


@pytest.mark.parametrize("attempt", range(3))
def test_two_simultaneous_joins_for_the_last_spot(
    db_session, creator, make_league, create_user, make_team, attempt
):
    league = make_league(creator, "Un lugar", max_participants=2)
    users = [create_user(f"racer{attempt}_{i}") for i in range(2)]
    teams = [make_team(u) for u in users]
    factory = sessionmaker(bind=db_session.get_bind())
    barrier = threading.Barrier(2)
    results, errors = [None, None], []

    def run(i):
        try:
            with factory() as session:
                members, coach_id = teams[i]
                barrier.wait(timeout=10)
                results[i] = SqlAlchemyLeagueRepository(session).join(
                    join_data(league.id, users[i].id, f"s{i}", members, coach_id)
                )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(i,), daemon=True) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, errors
    assert sorted(results, key=str) == [None, "leagueFull"]  # uno entra, el otro no
    assert participants_count(db_session, league.id) == 2
    loser = users[results.index("leagueFull")]
    assert team_of(db_session, league.id, loser.id) == []


def test_deleting_the_session_removes_its_unlocks(
    login_as, db_session, session_repo, private_league, joiner, team_body
):
    api = login_as(joiner)
    resp = api.post(url(private_league.id), json={**team_body, "password": PASSWORD})
    assert resp.status_code == 201
    session_repo.delete(session_of(api))  # log-out
    assert not is_unlocked(db_session, session_of(api), private_league.id)
    assert participant(db_session, private_league.id, joiner.id) is not None  # sigue inscripto
