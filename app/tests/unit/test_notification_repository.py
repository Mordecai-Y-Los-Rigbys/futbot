from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.domain.league import LeagueStatus
from app.domain.match import MatchStatus
from app.models.league import League
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.notification import Notification
from app.repositories.match_abstract import PenaltyShootoutData
from app.repositories.match_sqlalchemy import SqlAlchemyMatchRepository
from app.repositories.notification_sqlalchemy import SqlAlchemyNotificationRepository
from app.tests.conftest import ensure_user

START = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)


@pytest.fixture()
def users(db_session):
    return [ensure_user(db_session, uid) for uid in (1, 2, 3, 4)]


def add_league(db_session, member_ids, name="Liga") -> League:
    league = League(
        name=name,
        creator_id=member_ids[0],
        status=LeagueStatus.started,
        min_participants=2,
        max_participants=8,
        match_duration=2,
        private=False,
    )
    db_session.add(league)
    db_session.flush()
    db_session.add_all(LeagueParticipant(league_id=league.id, user_id=uid) for uid in member_ids)
    db_session.commit()
    return league


def add_match(db_session, league_id, user_1, user_2, minutes=0) -> Match:
    match = Match(
        league_id=league_id,
        user_1_id=user_1,
        user_2_id=user_2,
        status=MatchStatus.started,
        scheduled_at=START + timedelta(minutes=minutes) if league_id else None,
    )
    db_session.add(match)
    db_session.commit()
    return match


@pytest.fixture()
def league(db_session, users):
    """Liga de 3 participantes (1, 2 y 3) con dos partidos. El 4 no participa."""
    return add_league(db_session, [1, 2, 3])


def all_notifications(db_session) -> list[Notification]:
    db_session.expire_all()
    return list(db_session.scalars(select(Notification).order_by(Notification.id)))


def finish(db_session, match_id, score_1=1, score_2=0, penalties=None) -> bool:
    return SqlAlchemyMatchRepository(db_session).finish(match_id, score_1, score_2, penalties)


# --- creación -----------------------------------------------------------------


def test_a_finished_league_match_notifies_every_participant(db_session, league):
    first = add_match(db_session, league.id, 1, 2)
    add_match(db_session, league.id, 2, 3, minutes=10)

    assert finish(db_session, first.id) is False

    created = all_notifications(db_session)
    assert sorted(n.user_id for n in created) == [1, 2, 3]
    assert all(n.league_match_id == first.id and n.league_id == league.id for n in created)
    assert all(n.seen is False and n.created_at is not None for n in created)


def test_the_last_match_creates_the_match_and_then_the_league_notification(db_session, league):
    first = add_match(db_session, league.id, 1, 2)
    last = add_match(db_session, league.id, 2, 3, minutes=10)
    finish(db_session, first.id)

    assert finish(db_session, last.id) is True

    created = [n for n in all_notifications(db_session) if n.league_match_id != first.id]
    assert [n.league_match_id for n in created] == [last.id] * 3 + [None] * 3
    for user_id in (1, 2, 3):
        state = SqlAlchemyNotificationRepository(db_session).get_state(user_id)
        assert [n.league_match_id for n in state.notifications] == [None, last.id, first.id]


def test_a_friendly_creates_no_notifications(db_session, league):
    friendly = add_match(db_session, None, 1, 2)
    assert finish(db_session, friendly.id) is False
    assert all_notifications(db_session) == []


def test_a_failure_closing_the_league_leaves_no_notifications(db_session, league):
    last = add_match(db_session, league.id, 1, 2)
    repo = SqlAlchemyMatchRepository(db_session)
    add = repo._add_notifications

    def failing(league_id, league_match_id):
        add(league_id, league_match_id)
        if league_match_id is None:
            raise RuntimeError("falla al cerrar la liga")

    repo._add_notifications = failing
    with pytest.raises(RuntimeError):
        repo.finish(last.id, 1, 0)

    assert all_notifications(db_session) == []
    assert db_session.get(Match, last.id).status == MatchStatus.started
    assert db_session.get(League, league.id).status == LeagueStatus.started


def test_a_failed_commit_leaves_no_notifications(db_session, league, monkeypatch):
    match = add_match(db_session, league.id, 1, 2)
    add_match(db_session, league.id, 2, 3, minutes=10)

    def failing_commit():
        raise RuntimeError("falla el commit")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    with pytest.raises(RuntimeError):
        finish(db_session, match.id)
    monkeypatch.undo()

    assert all_notifications(db_session) == []
    assert db_session.get(Match, match.id).status == MatchStatus.started


# --- lectura ------------------------------------------------------------------


def add_notification(db_session, user_id, league_id, match_id=None, minutes=0, seen=False):
    n = Notification(
        user_id=user_id,
        league_id=league_id,
        league_match_id=match_id,
        seen=seen,
        created_at=START + timedelta(minutes=minutes),
    )
    db_session.add(n)
    db_session.commit()
    return n


def test_state_of_a_user_without_notifications(db_session, users):
    state = SqlAlchemyNotificationRepository(db_session).get_state(1)
    assert (state.has_unseen, state.notifications) == (False, [])


def test_only_the_10_most_recent_newest_first(db_session, league):
    created = [add_notification(db_session, 1, league.id, minutes=m) for m in range(12)]
    state = SqlAlchemyNotificationRepository(db_session).get_state(1)
    assert [n.id for n in state.notifications] == [n.id for n in reversed(created)][:10]


def test_same_date_is_ordered_by_id_descending(db_session, league):
    a = add_notification(db_session, 1, league.id)
    b = add_notification(db_session, 1, league.id)
    state = SqlAlchemyNotificationRepository(db_session).get_state(1)
    assert [n.id for n in state.notifications] == [b.id, a.id]


def test_an_unseen_one_outside_the_10_counts_for_has_unseen(db_session, league):
    add_notification(db_session, 1, league.id, minutes=0, seen=False)
    for m in range(1, 11):
        add_notification(db_session, 1, league.id, minutes=m, seen=True)
    state = SqlAlchemyNotificationRepository(db_session).get_state(1)
    assert all(n.seen for n in state.notifications)
    assert state.has_unseen is True


def test_all_seen_is_not_new(db_session, league):
    add_notification(db_session, 1, league.id, seen=True)
    assert SqlAlchemyNotificationRepository(db_session).get_state(1).has_unseen is False


def test_other_users_notifications_are_not_included(db_session, league):
    add_notification(db_session, 2, league.id)
    state = SqlAlchemyNotificationRepository(db_session).get_state(1)
    assert (state.has_unseen, state.notifications) == (False, [])


def test_a_match_notification_has_both_clubs_and_the_result(db_session, league):
    match = add_match(db_session, league.id, 1, 2)
    add_match(db_session, league.id, 2, 3, minutes=10)
    kicks = [{"club": "club1", "kickerId": 3, "kickerName": "J3", "round": 1, "scored": True}]
    shootout = PenaltyShootoutData(score_1=4, score_2=3, winner=1, kicks=kicks)
    finish(db_session, match.id, 2, 2, shootout)

    n = SqlAlchemyNotificationRepository(db_session).get_state(3).notifications[0]
    assert (n.league_id, n.league_match_id, n.seen) == (league.id, match.id, False)
    assert n.created_at.tzinfo is not None
    assert (n.match.club1.id, n.match.club1.club_name) == (1, "club1")
    assert (n.match.club2.id, n.match.club2.username) == (2, "user2")
    assert (n.match.score_1, n.match.score_2) == (2, 2)
    assert n.match.penalties == shootout


def test_a_match_without_shootout_has_no_penalties(db_session, league):
    match = add_match(db_session, league.id, 1, 2)
    add_match(db_session, league.id, 2, 3, minutes=10)
    finish(db_session, match.id, 3, 1)
    n = SqlAlchemyNotificationRepository(db_session).get_state(1).notifications[0]
    assert n.match.penalties is None


def test_a_league_notification_has_the_league_name(db_session, users):
    league = add_league(db_session, [1, 2], name="Copa")
    add_notification(db_session, 1, league.id)
    n = SqlAlchemyNotificationRepository(db_session).get_state(1).notifications[0]
    assert (n.league_match_id, n.match, n.league_name) == (None, None, "Copa")


def test_recipients_are_the_participants_of_the_league(db_session, league, users):
    other = add_league(db_session, [4], name="Otra")
    repo = SqlAlchemyNotificationRepository(db_session)
    assert sorted(repo.recipients(league.id)) == [1, 2, 3]
    assert repo.recipients(other.id) == [4]
