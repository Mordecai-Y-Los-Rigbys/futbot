import asyncio
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.api.ws_deps import get_friendly_expiry
from app.main import app
from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.models.team_member import TeamMember
from app.repositories.friendly_abstract import CreateFriendlyMemberData, JoinFriendlyData
from app.repositories.friendly_sqlalchemy import SqlAlchemyFriendlyRepository
from app.repositories.match_expiry_sqlalchemy import SqlAlchemyMatchExpiryRepository
from app.schemas.errors import Error, JoinFriendlyMatchBadRequest, JoinFriendlyMatchConflict

pytestmark = pytest.mark.integration

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]
ITEM_FIELDS = {
    "id", "leagueId", "name", "status", "club1", "club2",
    "scheduledAt", "createdAt", "result",
}


# --- fakes y fixtures -----------------------------------------------------------------------

class FakeExpiry:
    def __init__(self):
        self.scheduled = []
        self.unscheduled = []

    def schedule(self, match_id, created_at=None):
        self.scheduled.append(match_id)

    def unschedule(self, match_id):
        self.unscheduled.append(match_id)


@pytest.fixture()
def schedulers():
    expiry = FakeExpiry()
    app.dependency_overrides[get_friendly_expiry] = lambda: expiry
    yield expiry
    app.dependency_overrides.pop(get_friendly_expiry, None)


@pytest.fixture()
def creator(create_user):
    return create_user("creator", "Creator FC")


@pytest.fixture()
def joiner(create_user):
    return create_user("joiner")


@pytest.fixture()
def late(create_user):
    return create_user("late")


@pytest.fixture()
def other(create_user):
    return create_user("other")


@pytest.fixture()
def make_team(db_session, make_behaviors):
    """make_team(user) -> lista `members` lista para enviar (6 jugadores y 6 behaviors propios)."""

    def _make(user):
        players = [
            Player(user_id=user.id, name=f"J{i}", power=60, agility=60,
                   control=60, strength=60, speed=60)
            for i in range(6)
        ]
        db_session.add_all(players)
        db_session.commit()
        behaviors = make_behaviors(user.id, [f"b{user.id}_{i}" for i in range(6)])
        return [
            {"playerId": p.id, "role": r, "behaviorId": b.id}
            for p, r, b in zip(players, ROLES, behaviors)
        ]

    return _make


@pytest.fixture()
def joiner_team(joiner, make_team):
    return make_team(joiner)


@pytest.fixture()
def late_team(late, make_team):
    return make_team(late)


@pytest.fixture()
def friendly(login_as, creator, make_team, schedulers):
    """Amistoso creado con POST /friendlies. Devuelve (respuesta del POST, members del creador)."""
    members = make_team(creator)
    resp = login_as(creator).post(
        "/friendlies", json={"name": "Partido amistoso 1", "members": members}
    )
    assert resp.status_code == 201, resp.text
    return resp.json(), members


def url(match_id):
    return f"/friendlies/{match_id}/members"


def add_match(db_session, **fields) -> Match:
    match = Match(**fields)
    db_session.add(match)
    db_session.commit()
    return match


def match_row(db_session, match_id) -> Match:
    db_session.expire_all()
    return db_session.get(Match, match_id)


def members_of(db_session, match_id, user_id):
    db_session.expire_all()
    return db_session.scalars(
        select(TeamMember).where(
            TeamMember.match_id == match_id, TeamMember.user_id == user_id
        )
    ).all()


def team_of(rows):
    return sorted((m.player_id, m.behavior_id, m.role.value) for m in rows)


def expected_team(members):
    return sorted((m["playerId"], m["behaviorId"], m["role"]) for m in members)


def assert_untouched(db_session, match_id, user):
    match = match_row(db_session, match_id)
    assert match.user_2_id is None and match.status == MatchStatus.scheduled
    assert members_of(db_session, match_id, user.id) == []


def to_data(match_id, user_id, members):
    return JoinFriendlyData(
        match_id=match_id,
        user_id=user_id,
        members=[
            CreateFriendlyMemberData(
                player_id=m["playerId"], behavior_id=m["behaviorId"], role=m["role"]
            )
            for m in members
        ],
    )


# --- unión exitosa ------------------------------------------------------------------------------------

def test_join_keeps_the_same_match_and_registers_the_rival(
    login_as, db_session, creator, joiner, friendly, joiner_team, schedulers
):
    created, creator_members = friendly
    expiry = schedulers
    resp = login_as(joiner).post(url(created["id"]), json={"members": joiner_team})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == ITEM_FIELDS
    assert body["id"] == created["id"]
    assert body["createdAt"] == created["createdAt"]  # no se reemplaza
    assert body["name"] == created["name"]
    assert body["status"] == "scheduled"
    assert body["leagueId"] is None and body["scheduledAt"] is None and body["result"] is None
    assert body["club1"] == created["club1"]
    assert body["club2"] == {"id": joiner.id, "username": "joiner", "name": "club-joiner"}

    match = match_row(db_session, created["id"])
    assert (match.user_1_id, match.user_2_id) == (creator.id, joiner.id)
    assert match.status == MatchStatus.scheduled
    assert db_session.query(Match).count() == 1  # no se crea otro partido

    assert expiry.unscheduled == [created["id"]]


def test_both_teams_are_persisted_and_the_creators_is_kept(
    login_as, db_session, creator, joiner, friendly, joiner_team
):
    created, creator_members = friendly
    login_as(joiner).post(url(created["id"]), json={"members": joiner_team})
    assert team_of(members_of(db_session, created["id"], creator.id)) == expected_team(creator_members)
    assert team_of(members_of(db_session, created["id"], joiner.id)) == expected_team(joiner_team)


def test_the_same_behavior_can_be_reused_for_several_players(
    login_as, db_session, joiner, friendly, joiner_team
):
    created, _ = friendly
    shared = joiner_team[0]["behaviorId"]
    members = [{**m, "behaviorId": shared} for m in joiner_team]
    resp = login_as(joiner).post(url(created["id"]), json={"members": members})
    assert resp.status_code == 200, resp.text
    assert {m.behavior_id for m in members_of(db_session, created["id"], joiner.id)} == {shared}


def test_joined_match_disappears_from_the_listing(
    login_as, create_user, joiner, friendly, joiner_team
):
    created, _ = friendly
    viewer = login_as(create_user("viewer"))
    assert [i["id"] for i in viewer.get("/friendlies").json()["items"]] == [created["id"]]
    assert login_as(joiner).post(url(created["id"]), json={"members": joiner_team}).status_code == 200
    body = viewer.get("/friendlies").json()
    assert body["items"] == [] and body["total"] == 0


def test_second_join_is_not_joinable_and_keeps_the_first_rival(
    login_as, db_session, joiner, late, friendly, joiner_team, late_team, schedulers
):
    created, _ = friendly
    assert login_as(joiner).post(url(created["id"]), json={"members": joiner_team}).status_code == 200
    resp = login_as(late).post(url(created["id"]), json={"members": late_team})
    assert resp.status_code == 409 and resp.json()["code"] == "notJoinable"
    assert match_row(db_session, created["id"]).user_2_id == joiner.id
    assert members_of(db_session, created["id"], late.id) == []


# --- autenticación y ids de ruta -------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/friendlies/1/members", "/friendlies/abc/members", "/friendlies/0/members"])
def test_no_cookie_is_401_even_with_bad_id_or_body(client, path):
    resp = client.post(path, json={"members": 5})
    assert resp.status_code == 401 and resp.json()["code"] is None
    Error.model_validate(resp.json())


def test_nonexistent_session_is_401(client):
    client.cookies.set("session_id", "no-existe")
    assert client.post("/friendlies/1/members", json={}).status_code == 401


def test_expired_session_is_401(login_as, create_user):
    expired = login_as(create_user("u"), expires_in=timedelta(days=-1))
    assert expired.post("/friendlies/1/members", json={}).status_code == 401


@pytest.mark.parametrize("raw_id", ["abc", "1.5", "0", "-1", "2147483648", "99999999999999999999"])
def test_invalid_route_id_is_404_even_with_invalid_body(login_as, joiner, raw_id):
    api = login_as(joiner)
    for kwargs in ({"json": {"members": 5}}, {}):
        resp = api.post(f"/friendlies/{raw_id}/members", **kwargs)
        assert resp.status_code == 404 and resp.json()["code"] is None


def test_nonexistent_match_is_404(login_as, joiner, joiner_team):
    resp = login_as(joiner).post(url(999999), json={"members": joiner_team})
    assert resp.status_code == 404
    assert resp.json() == {"code": None, "message": "Partido amistoso no encontrado."}


def test_league_match_is_404(login_as, db_session, creator, joiner, other, joiner_team, make_league):
    league = make_league(creator, "Liga")
    match = add_match(
        db_session, league_id=league.id, user_1_id=creator.id, user_2_id=other.id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    resp = login_as(joiner).post(url(match.id), json={"members": joiner_team})
    assert resp.status_code == 404


# --- validación del body (400) ----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({}, "incompleteForm"),
        ({"content": "{", "headers": {"Content-Type": "application/json"}}, "incompleteForm"),
        ({"json": []}, "incompleteForm"),
        ({"json": {}}, "incompleteForm"),
        ({"json": {"members": "x"}}, "invalidFieldType"),
        ({"json": {"members": [{"playerId": 0, "role": "forward", "behaviorId": 1}]}}, "invalidFieldType"),
        ({"json": {"members": []}}, "invalidTeam"),
    ],
)
def test_body_errors_are_400_and_persist_nothing(
    login_as, db_session, joiner, friendly, kwargs, code
):
    created, _ = friendly
    resp = login_as(joiner).post(url(created["id"]), **kwargs)
    assert resp.status_code == 400
    assert resp.json()["code"] == code
    JoinFriendlyMatchBadRequest.model_validate(resp.json())
    assert_untouched(db_session, created["id"], joiner)


def test_400_beats_409_own_match(login_as, creator, friendly):
    created, _ = friendly
    resp = login_as(creator).post(url(created["id"]), json={"members": []})
    assert resp.status_code == 400 and resp.json()["code"] == "invalidTeam"


# --- conflictos (409) ----------------------------------------------------------------------------------------

STATES = {
    "with_rival": lambda other: dict(user_2_id=other.id),
    "started": lambda other: dict(user_2_id=other.id, status=MatchStatus.started),
    "finished": lambda other: dict(
        user_2_id=other.id, status=MatchStatus.finished, score_1=1, score_2=0
    ),
    "cancelled": lambda other: dict(status=MatchStatus.cancelled),
}


@pytest.mark.parametrize("kind", list(STATES))
def test_match_that_does_not_admit_a_rival_is_not_joinable(
    login_as, db_session, creator, joiner, other, joiner_team, kind
):
    match = add_match(db_session, user_1_id=creator.id, name="X", **STATES[kind](other))
    before = match_row(db_session, match.id)
    snapshot = (before.user_2_id, before.status)
    resp = login_as(joiner).post(url(match.id), json={"members": joiner_team})
    assert resp.status_code == 409 and resp.json()["code"] == "notJoinable"
    JoinFriendlyMatchConflict.model_validate(resp.json())
    after = match_row(db_session, match.id)
    assert (after.user_2_id, after.status) == snapshot
    assert members_of(db_session, match.id, joiner.id) == []


def test_match_cancelled_by_expiry_is_not_joinable(
    login_as, db_session, joiner, friendly, joiner_team
):
    created, _ = friendly
    assert SqlAlchemyMatchExpiryRepository(db_session).cancel_if_waiting_friendly(created["id"])
    resp = login_as(joiner).post(url(created["id"]), json={"members": joiner_team})
    assert resp.status_code == 409 and resp.json()["code"] == "notJoinable"
    match = match_row(db_session, created["id"])
    assert match.status == MatchStatus.cancelled and match.user_2_id is None
    assert members_of(db_session, created["id"], joiner.id) == []


def test_creator_cannot_join_their_own_match(login_as, db_session, creator, friendly):
    created, creator_members = friendly
    resp = login_as(creator).post(url(created["id"]), json={"members": creator_members})
    assert resp.status_code == 409 and resp.json()["code"] == "isOwnMatch"
    assert match_row(db_session, created["id"]).user_2_id is None
    assert len(members_of(db_session, created["id"], creator.id)) == 6  # sin duplicar


def test_user_waiting_in_another_friendly_is_already_playing(
    login_as, db_session, joiner, friendly, joiner_team
):
    created, _ = friendly
    api = login_as(joiner)
    own = api.post("/friendlies", json={"name": "Mio", "members": joiner_team})
    assert own.status_code == 201, own.text
    resp = api.post(url(created["id"]), json={"members": joiner_team})
    assert resp.status_code == 409 and resp.json()["code"] == "alreadyPlaying"
    assert_untouched(db_session, created["id"], joiner)


def test_user_in_a_started_match_is_already_playing(
    login_as, db_session, joiner, other, friendly, joiner_team
):
    created, _ = friendly
    add_match(db_session, user_1_id=other.id, user_2_id=joiner.id, status=MatchStatus.started)
    resp = login_as(joiner).post(url(created["id"]), json={"members": joiner_team})
    assert resp.status_code == 409 and resp.json()["code"] == "alreadyPlaying"
    assert_untouched(db_session, created["id"], joiner)


def test_foreign_players_are_not_owned(login_as, db_session, joiner, friendly):
    created, creator_members = friendly
    resp = login_as(joiner).post(url(created["id"]), json={"members": creator_members})
    assert resp.status_code == 409 and resp.json()["code"] == "playerOrBehaviorNotOwned"
    assert_untouched(db_session, created["id"], joiner)


def test_foreign_behavior_is_not_owned(login_as, db_session, joiner, friendly, joiner_team):
    created, creator_members = friendly
    mixed = [{**m, "behaviorId": c["behaviorId"]} for m, c in zip(joiner_team, creator_members)]
    resp = login_as(joiner).post(url(created["id"]), json={"members": mixed})
    assert resp.status_code == 409 and resp.json()["code"] == "playerOrBehaviorNotOwned"
    assert_untouched(db_session, created["id"], joiner)


def test_nonexistent_ids_are_not_owned(login_as, db_session, joiner, friendly, joiner_team):
    created, _ = friendly
    members = [dict(m) for m in joiner_team]
    members[0]["playerId"] = 2147483647
    resp = login_as(joiner).post(url(created["id"]), json={"members": members})
    assert resp.status_code == 409 and resp.json()["code"] == "playerOrBehaviorNotOwned"
    assert_untouched(db_session, created["id"], joiner)


# --- repositorio: unión condicional ----------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", list(STATES))
def test_repo_join_returns_none_when_the_match_does_not_admit_a_rival(
    db_session, creator, joiner, other, joiner_team, kind
):
    match = add_match(db_session, user_1_id=creator.id, name="X", **STATES[kind](other))
    before = (match_row(db_session, match.id).user_2_id, match_row(db_session, match.id).status)
    repo = SqlAlchemyFriendlyRepository(db_session)
    assert repo.join_friendly(to_data(match.id, joiner.id, joiner_team)) is None
    after = match_row(db_session, match.id)
    assert (after.user_2_id, after.status) == before
    assert members_of(db_session, match.id, joiner.id) == []


def test_repo_join_rejects_the_creator(db_session, creator, friendly):
    created, creator_members = friendly
    repo = SqlAlchemyFriendlyRepository(db_session)
    assert repo.join_friendly(to_data(created["id"], creator.id, creator_members)) is None
    assert match_row(db_session, created["id"]).user_2_id is None


def test_repo_get_friendly_state(db_session, creator, other, friendly, make_league):
    created, _ = friendly
    repo = SqlAlchemyFriendlyRepository(db_session)
    st = repo.get_friendly_state(created["id"])
    assert (st.id, st.creator_id, st.rival_id, st.status) == (created["id"], creator.id, None, "scheduled")
    assert repo.get_friendly_state(999999) is None
    league = make_league(creator, "Liga")
    league_match = add_match(
        db_session, league_id=league.id, user_1_id=creator.id, user_2_id=other.id,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    assert repo.get_friendly_state(league_match.id) is None  # no es un amistoso


# --- atomicidad ------------------------------------------------------------------------------------------------------------

def test_failure_while_saving_the_team_rolls_back_the_join(
    db_session, creator, joiner, friendly, joiner_team
):
    created, _ = friendly
    repo = SqlAlchemyFriendlyRepository(db_session)
    bad = [
        {"playerId": 2147483000 + i, "role": r, "behaviorId": 2147483000 + i}
        for i, r in enumerate(ROLES)
    ]
    with pytest.raises(IntegrityError):  # FK: esos jugadores no existen
        repo.join_friendly(to_data(created["id"], joiner.id, bad))

    assert_untouched(db_session, created["id"], joiner)
    assert len(members_of(db_session, created["id"], creator.id)) == 6
    # el partido sigue admitiendo rival
    assert repo.join_friendly(to_data(created["id"], joiner.id, joiner_team)) is not None


def test_unexpected_error_rolls_back_the_join(
    db_session, monkeypatch, joiner, friendly, joiner_team
):
    created, _ = friendly
    repo = SqlAlchemyFriendlyRepository(db_session)

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(db_session, "add_all", boom)  # falla después del UPDATE
    with pytest.raises(RuntimeError):
        repo.join_friendly(to_data(created["id"], joiner.id, joiner_team))
    monkeypatch.undo()

    assert_untouched(db_session, created["id"], joiner)


# --- concurrencia (dos sesiones reales) --------------------------------------------------------------------------------------

def run_in_parallel(fns):
    from queue import Queue
    from time import monotonic

    barrier = threading.Barrier(len(fns))
    outcomes = Queue()

    def runner(index, fn):
        try:
            barrier.wait(timeout=10)
            result = fn()
        except BaseException as exc:
            outcomes.put((index, False, exc))
        else:
            outcomes.put((index, True, result))

    threads = [
        threading.Thread(
            target=runner,
            args=(index, fn),
            name=f"friendly-race-{index}",
            daemon=True,
        )
        for index, fn in enumerate(fns)
    ]

    for thread in threads:
        thread.start()

    deadline = monotonic() + 30
    for thread in threads:
        thread.join(timeout=max(0, deadline - monotonic()))

    alive = [thread.name for thread in threads if thread.is_alive()]
    assert not alive, f"Workers bloqueados al vencer el timeout: {alive}"

    assert outcomes.qsize() == len(fns), "Faltan resultados de los workers"

    results = [None] * len(fns)
    failures = []

    for _ in fns:
        index, succeeded, value = outcomes.get_nowait()
        if succeeded:
            results[index] = value
        else:
            failures.append((index, value))

    assert not failures, f"Errores en los workers: {failures}"
    return results


def join_in_own_session(db_session, match_id, user_id, members):
    factory = sessionmaker(bind=db_session.get_bind())

    def run():
        with factory() as session:
            return SqlAlchemyFriendlyRepository(session).join_friendly(
                to_data(match_id, user_id, members)
            )

    return run


def cancel_in_own_session(db_session, match_id):
    factory = sessionmaker(bind=db_session.get_bind())

    def run():
        with factory() as session:
            return SqlAlchemyMatchExpiryRepository(session).cancel_if_waiting_friendly(match_id)

    return run


@pytest.mark.parametrize("attempt", range(3))
def test_two_simultaneous_joins_only_one_wins(
    db_session, creator, joiner, late, friendly, joiner_team, late_team, attempt
):
    created, _ = friendly
    results = run_in_parallel([
        join_in_own_session(db_session, created["id"], joiner.id, joiner_team),
        join_in_own_session(db_session, created["id"], late.id, late_team),
    ])
    winners = [r for r in results if r is not None]
    assert len(winners) == 1  # el otro recibe notJoinable
    winner_id = winners[0].club2.id
    loser_id = ({joiner.id, late.id} - {winner_id}).pop()

    assert match_row(db_session, created["id"]).user_2_id == winner_id
    assert len(members_of(db_session, created["id"], winner_id)) == 6
    assert members_of(db_session, created["id"], loser_id) == []
    assert len(members_of(db_session, created["id"], creator.id)) == 6


def test_join_vs_expiry_race_has_a_single_consistent_outcome(
    db_session, creator, joiner, joiner_team
):
    for i in range(10):
        match = add_match(db_session, user_1_id=creator.id, name=f"Carrera {i}")
        joined, cancelled = run_in_parallel([
            join_in_own_session(db_session, match.id, joiner.id, joiner_team),
            cancel_in_own_session(db_session, match.id),
        ])
        row = match_row(db_session, match.id)
        if joined is not None:
            assert cancelled is False
            assert row.status == MatchStatus.scheduled and row.user_2_id == joiner.id
            assert len(members_of(db_session, match.id, joiner.id)) == 6
        else:
            assert cancelled is True
            assert row.status == MatchStatus.cancelled and row.user_2_id is None
            assert members_of(db_session, match.id, joiner.id) == []  # sin rival en un cancelado


# --- cuenta regresiva y arranque (tiempo controlado) -------------------------------------------------------------------

def status_of(db_session, match_id):
    db_session.expire_all()
    return db_session.scalar(select(Match.status).where(Match.id == match_id))


# --- repositorio de arranque ---------------------------------------------------------------------------------------------------
    
def test_nonexistent_behavior_rejects_join_without_side_effects(
    login_as, db_session, joiner, friendly, joiner_team, schedulers
):
    created, creator_members = friendly
    expiry = schedulers

    expiry_before = list(expiry.unscheduled)

    # Crear y eliminar un behavior para obtener un ID que sabemos inexistente.
    from app.models.behavior import Behavior

    behavior_id = joiner_team[0]["behaviorId"]
    behavior = db_session.get(Behavior, behavior_id)
    assert behavior is not None
    db_session.delete(behavior)
    db_session.commit()

    response = login_as(joiner).post(
        url(created["id"]),
        json={"members": joiner_team},
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "playerOrBehaviorNotOwned"
    assert_untouched(db_session, created["id"], joiner)

    assert team_of(
        members_of(db_session, created["id"], created["club1"]["id"])
    ) == expected_team(creator_members)

    assert expiry.unscheduled == expiry_before


def test_same_owned_behavior_can_be_persisted_for_all_six_players(
    login_as, db_session, joiner, friendly, joiner_team
):
    created, _ = friendly
    behavior_id = joiner_team[0]["behaviorId"]
    members = [
        {**member, "behaviorId": behavior_id}
        for member in joiner_team
    ]

    response = login_as(joiner).post(
        url(created["id"]),
        json={"members": members},
    )

    assert response.status_code == 200, response.text
    assert response.json()["club2"]["id"] == joiner.id

    persisted = members_of(db_session, created["id"], joiner.id)
    assert len(persisted) == 6
    assert team_of(persisted) == expected_team(members)
    assert {member.behavior_id for member in persisted} == {behavior_id}