import threading
from datetime import datetime, timedelta, timezone
from itertools import combinations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.api.ws_deps import get_league_match_start
from app.domain.match import MatchStatus
from app.main import app
from app.models.league import League, LeagueStatus
from app.models.match import Match
from app.repositories.league_abstract import FixtureMatchData, JoinLeagueData
from app.repositories.league_sqlalchemy import SqlAlchemyLeagueRepository

pytestmark = pytest.mark.integration


class FakeLeagueMatchStart:
    def __init__(self):
        self.leagues = []

    async def schedule_league(self, league_id):
        self.leagues.append(league_id)


@pytest.fixture(autouse=True)
def match_start():
    fake = FakeLeagueMatchStart()
    app.dependency_overrides[get_league_match_start] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_league_match_start, None)


@pytest.fixture()
def creator(create_user):
    return create_user("creator")


@pytest.fixture()
def league(creator, make_league, create_user, add_participant):
    lg = make_league(creator)
    for name in ("p2", "p3"):
        add_participant(lg, create_user(name))
    return lg


def url(league_id):
    return f"/leagues/{league_id}/start"


def matches_of(db_session, league_id) -> list[Match]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(Match).where(Match.league_id == league_id).order_by(Match.scheduled_at)
        )
    )


def status_of(db_session, league_id) -> LeagueStatus:
    db_session.expire_all()
    return db_session.get(League, league_id).status


def set_league(db_session, league, **fields):
    for k, v in fields.items():
        setattr(league, k, v)
    db_session.commit()


def utc(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def assert_untouched(db_session, league_id, status=LeagueStatus.preparation):
    assert status_of(db_session, league_id) == status
    assert matches_of(db_session, league_id) == []


def test_creator_starts_the_league_and_the_fixture_is_saved(login_as, db_session, creator, league):
    resp = login_as(creator).post(url(league.id))
    assert resp.status_code == 204, resp.text
    assert resp.content == b""

    assert status_of(db_session, league.id) == LeagueStatus.started
    matches = matches_of(db_session, league.id)
    assert len(matches) == 3
    for m in matches:
        assert m.status == MatchStatus.scheduled
        assert (m.score_1, m.score_2, m.seed) == (None, None, None)
        assert m.user_1_id != m.user_2_id
        assert m.scheduled_at is not None


def test_penalties_mode_leaves_room_for_the_shootout(login_as, db_session, creator, league):
    set_league(db_session, league, allow_draws=False, match_duration=5)
    assert login_as(creator).post(url(league.id)).status_code == 204
    times = [utc(m.scheduled_at) for m in matches_of(db_session, league.id)]
    assert times[1] - times[0] == timedelta(minutes=8, seconds=55)


def test_no_session_is_401(db_session, client, league):
    resp = client.post(url(league.id))
    assert resp.status_code == 401 and resp.json()["code"] is None
    assert_untouched(db_session, league.id)


@pytest.mark.parametrize("raw_id", ["abc", "999999"])
def test_invalid_or_nonexistent_id_is_404(login_as, creator, raw_id):
    resp = login_as(creator).post(url(raw_id))
    assert resp.status_code == 404 and resp.json()["code"] is None


def test_a_participant_who_is_not_the_creator_cannot_start_it(
    login_as, db_session, league, create_user, add_participant
):
    participant = create_user("participant")
    add_participant(league, participant)
    resp = login_as(participant).post(url(league.id))
    assert resp.status_code == 403 and resp.json()["code"] is None
    assert_untouched(db_session, league.id)


@pytest.mark.parametrize("status", ["started", "cancelled", "finished"])
def test_league_not_in_preparation(login_as, db_session, creator, league, status):
    set_league(db_session, league, status=LeagueStatus(status))
    resp = login_as(creator).post(url(league.id))
    assert resp.status_code == 409 and resp.json()["code"] == "notInPreparation"
    assert_untouched(db_session, league.id, LeagueStatus(status))


def test_not_enough_participants(
    login_as, db_session, creator, make_league, create_user, add_participant
):
    lg = make_league(creator)
    add_participant(lg, create_user("solo"))
    resp = login_as(creator).post(url(lg.id))
    assert resp.status_code == 409 and resp.json()["code"] == "notEnoughParticipants"
    assert_untouched(db_session, lg.id)


def run_together(*jobs):
    """Corre cada job en su propio thread, arrancando a la vez. Devuelve sus resultados."""
    barrier = threading.Barrier(len(jobs))
    results, errors = [None] * len(jobs), []

    def run(i):
        try:
            barrier.wait(timeout=10)
            results[i] = jobs[i]()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(i,), daemon=True) for i in range(len(jobs))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors, errors
    return results


def plan_all_pairs(ids):
    """Plan simple para los tests del repo: todos los pares, uno por minuto."""
    now = datetime.now(timezone.utc)
    return [
        FixtureMatchData(user_1_id=a, user_2_id=b, scheduled_at=now + timedelta(minutes=i))
        for i, (a, b) in enumerate(combinations(ids, 2))
    ]


def test_repo_get_start_state(db_session, create_user, make_league, add_participant):
    create_user("first")  # para que el id del creador no coincida con el de la liga
    owner = create_user("owner")
    lg = make_league(owner)
    for name in ("a", "b", "c"):
        add_participant(lg, create_user(name))
    set_league(db_session, lg, match_duration=2, allow_draws=False, min_participants=4)

    repo = SqlAlchemyLeagueRepository(db_session)
    st = repo.get_start_state(lg.id)
    assert (st.creator_id, st.status) == (owner.id, LeagueStatus.preparation)
    assert (st.min_participants, st.participants_count) == (4, 4)
    assert (st.match_duration, st.allow_draws) == (2, False)
    assert repo.get_start_state(2147483647) is None


def test_repo_rereads_a_state_changed_by_another_session(db_session, league):
    repo = SqlAlchemyLeagueRepository(db_session)
    assert repo.get_start_state(league.id).conflict() is None  # la liga queda en esta sesión
    with sessionmaker(bind=db_session.get_bind())() as other:  # otra request la cancela
        other.get(League, league.id).status = LeagueStatus.cancelled
        other.commit()
    assert repo.start(league.id, plan_all_pairs) == "notInPreparation"
    assert matches_of(db_session, league.id) == []


def test_failure_while_saving_the_fixture_rolls_back_everything(db_session, league):
    def bad_plan(ids):
        return [
            FixtureMatchData(user_1_id=ids[0], user_2_id=ids[0], scheduled_at=league.created_at)
        ]

    with pytest.raises(IntegrityError):
        SqlAlchemyLeagueRepository(db_session).start(league.id, bad_plan)
    assert_untouched(db_session, league.id)


@pytest.mark.parametrize("attempt", range(3))
def test_two_simultaneous_starts_generate_one_fixture(db_session, league, attempt):
    factory = sessionmaker(bind=db_session.get_bind())

    def start():
        with factory() as session:
            return SqlAlchemyLeagueRepository(session).start(league.id, plan_all_pairs)

    results = run_together(start, start)
    assert sorted(results, key=str) == [None, "notInPreparation"]
    assert len(matches_of(db_session, league.id)) == 3


@pytest.mark.parametrize("attempt", range(3))
def test_simultaneous_join_ends_up_in_the_fixture_or_gets_409(
    db_session, league, create_user, attempt
):
    joiner = create_user(f"late{attempt}")
    factory = sessionmaker(bind=db_session.get_bind())

    def start():
        with factory() as session:
            return SqlAlchemyLeagueRepository(session).start(league.id, plan_all_pairs)

    def join():
        with factory() as session:
            return SqlAlchemyLeagueRepository(session).join(
                JoinLeagueData(
                    league_id=league.id,
                    user_id=joiner.id,
                    session_id="s",
                    members=[],
                    coach_behavior_id=None,
                    unlock_session=False,
                )
            )

    started, joined = run_together(start, join)
    assert started is None
    players = {u for m in matches_of(db_session, league.id) for u in (m.user_1_id, m.user_2_id)}
    if joined is None:  # entró antes del inicio: juega
        assert joiner.id in players and len(matches_of(db_session, league.id)) == 6
    else:  # llegó tarde: 409 y queda afuera
        assert joined == "notInPreparation"
        assert joiner.id not in players and len(matches_of(db_session, league.id)) == 3
