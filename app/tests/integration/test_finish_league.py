import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.domain.league import LeagueStatus
from app.domain.match import MatchStatus
from app.models.league import League
from app.models.match import Match
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository

pytestmark = pytest.mark.integration

START = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)


@pytest.fixture()
def players(create_user):
    return [create_user(f"p{i}") for i in range(3)]


@pytest.fixture()
def league(db_session, players, make_league, add_participant):
    """Liga en curso con 3 participantes y sus 3 partidos `scheduled`."""
    creator, *others = players
    lg = make_league(creator, status="started")
    for user in others:
        add_participant(lg, user)
    pairs = [(0, 1), (0, 2), (1, 2)]
    db_session.add_all(
        Match(
            league_id=lg.id,
            user_1_id=players[a].id,
            user_2_id=players[b].id,
            scheduled_at=START + timedelta(minutes=10 * i),
        )
        for i, (a, b) in enumerate(pairs)
    )
    db_session.commit()
    return lg


def match_ids(db_session, league_id) -> list[int]:
    return list(
        db_session.scalars(select(Match.id).where(Match.league_id == league_id).order_by(Match.id))
    )


def finish(db_session, match_id, score_1=1, score_2=0) -> bool:
    return SqlAlchemyMatchRepository(db_session).finish(match_id, score_1, score_2)


def status_of(db_session, league_id) -> LeagueStatus:
    db_session.expire_all()
    return db_session.get(League, league_id).status


def test_the_last_match_finishes_the_league(db_session, league):
    first, second, last = match_ids(db_session, league.id)
    finish(db_session, first)
    finish(db_session, second)

    assert finish(db_session, last, 2, 3) is True
    assert status_of(db_session, league.id) == LeagueStatus.finished
    match = db_session.get(Match, last)
    assert (match.status, match.score_1, match.score_2) == (MatchStatus.finished, 2, 3)


def test_a_match_that_is_not_the_last_does_not_finish_the_league(db_session, league):
    first, second, third = match_ids(db_session, league.id)
    db_session.get(Match, third).status = MatchStatus.started  # se está jugando
    db_session.commit()

    assert finish(db_session, first) is False
    assert finish(db_session, second) is False
    assert status_of(db_session, league.id) == LeagueStatus.started


def test_a_league_that_is_not_started_does_not_change(db_session, league):
    first, second, last = match_ids(db_session, league.id)
    finish(db_session, first)
    finish(db_session, second)
    league.status = LeagueStatus.cancelled
    db_session.commit()

    assert finish(db_session, last) is False
    assert status_of(db_session, league.id) == LeagueStatus.cancelled


def test_two_last_matches_finishing_at_once_finish_the_league_once(db_session, league):
    first, second, third = match_ids(db_session, league.id)
    finish(db_session, first)
    factory = sessionmaker(bind=db_session.get_bind())
    second_saved = threading.Event()
    results, errors = {}, []

    def run(match_id, before_check):
        try:
            with factory() as session:
                repo = SqlAlchemyMatchRepository(session)
                check = repo._finish_league_if_done

                def paused_check(league_id):
                    before_check()
                    return check(league_id)

                repo._finish_league_if_done = paused_check
                results[match_id] = repo.finish(match_id, 0, 0)
        except BaseException as exc:
            errors.append(exc)

    # El primero guarda su resultado y espera, antes de contar los pendientes,
    # a que el segundo guarde el suyo. Con la liga bloqueada, el segundo no
    # puede: el primero sigue a los 0,5 s y el segundo cuenta después.
    first_thread = threading.Thread(
        target=run, args=(second, lambda: second_saved.wait(timeout=0.5)), daemon=True
    )
    second_thread = threading.Thread(target=run, args=(third, second_saved.set), daemon=True)
    first_thread.start()
    time.sleep(0.1)  # que el primero llegue a la pausa
    second_thread.start()
    for t in (first_thread, second_thread):
        t.join(timeout=10)

    assert not errors, errors
    assert results == {second: False, third: True}  # la termina uno solo, el último
    assert status_of(db_session, league.id) == LeagueStatus.finished
