"""POST /notifications/seen contra la base real (Postgres), con el canal real."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.api import ws_notification_deps
from app.models.notification import Notification
from app.tests.league_ws_helpers import ORIGIN, connect, stays_silent

pytestmark = pytest.mark.integration

URL = "/notifications/seen"
WS = "/ws/notifications"
START = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def wiring(client, db_session, monkeypatch):
    """Cableado real; solo se redirige SessionLocal del canal a la base de tests."""
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_session.get_bind())
    monkeypatch.setattr(ws_notification_deps, "SessionLocal", factory)
    monkeypatch.setenv("ALLOWED_ORIGINS", ORIGIN)


@pytest.fixture()
def me(create_user):
    return create_user("me")


@pytest.fixture()
def other(create_user):
    return create_user("other")


@pytest.fixture()
def league(make_league, me, other, add_participant):
    lg = make_league(me, name="Copa")
    add_participant(lg, other)
    return lg


@pytest.fixture()
def add(db_session, league):
    def _add(user, minutes=0, seen=False) -> Notification:
        n = Notification(
            user_id=user.id,
            league_id=league.id,
            seen=seen,
            created_at=START + timedelta(minutes=minutes),
        )
        db_session.add(n)
        db_session.commit()
        return n

    return _add


def seen_of(db_session, user) -> dict[int, bool]:
    db_session.expire_all()
    rows = db_session.scalars(select(Notification).where(Notification.user_id == user.id))
    return {n.id: n.seen for n in rows}


def post(api, body):
    return api.post(URL, json=body)


# --- 204 ----------------------------------------------------------------------


def test_marks_the_given_one_and_the_older_ones_but_not_the_newer(
    login_as, db_session, me, add
):
    a, b, c = add(me, 0), add(me, 5), add(me, 10)
    assert post(login_as(me), {"notificationId": b.id}).status_code == 204
    assert seen_of(db_session, me) == {a.id: True, b.id: True, c.id: False}


def test_other_users_notifications_are_not_touched(login_as, db_session, me, other, add):
    theirs = add(other, 0)
    mine = add(me, 5)
    assert post(login_as(me), {"notificationId": mine.id}).status_code == 204
    assert seen_of(db_session, other) == {theirs.id: False}


def test_repeating_the_request_is_204(login_as, db_session, me, add):
    n = add(me)
    api = login_as(me)
    assert post(api, {"notificationId": n.id}).status_code == 204
    assert post(api, {"notificationId": n.id}).status_code == 204
    assert seen_of(db_session, me) == {n.id: True}


# --- canal --------------------------------------------------------------------


def test_open_connections_of_every_session_receive_the_update(login_as, me, other, add):
    n = add(me)
    add(other)
    mine, second, theirs = login_as(me), login_as(me), login_as(other)
    with connect(mine, WS) as a, connect(second, WS) as b, connect(theirs, WS) as c:
        assert a.receive_json()["new"] is True
        assert b.receive_json()["new"] is True
        assert c.receive_json()["new"] is True

        assert post(mine, {"notificationId": n.id}).status_code == 204

        for ws in (a, b):
            message = ws.receive_json()
            assert message["new"] is False
            assert message["notifications"][0]["seen"] is True
        assert stays_silent(c)


def test_new_stays_true_if_a_newer_one_is_still_unseen(login_as, me, add):
    older = add(me, 0)
    add(me, 5)
    api = login_as(me)
    with connect(api, WS) as ws:
        ws.receive_json()
        assert post(api, {"notificationId": older.id}).status_code == 204
        message = ws.receive_json()
        assert message["new"] is True
        assert [n["seen"] for n in message["notifications"]] == [False, True]


def test_a_rejected_request_sends_nothing(login_as, me, other, add):
    theirs = add(other)
    api = login_as(me)
    with connect(api, WS) as ws:
        ws.receive_json()
        assert post(api, {"notificationId": theirs.id}).status_code == 409
        assert post(api, {"notificationId": 0}).status_code == 400
        assert stays_silent(ws)


# --- 401 ----------------------------------------------------------------------


@pytest.mark.parametrize("body", [{"notificationId": 1}, {"notificationId": "x"}, None])
def test_no_cookie_is_401_even_with_an_invalid_body(client, body):
    r = client.post(URL, json=body)
    assert (r.status_code, r.json()["code"]) == (401, None)


def test_expired_session_is_401(login_as, me, add):
    n = add(me)
    r = post(login_as(me, expires_in=timedelta(days=-1)), {"notificationId": n.id})
    assert (r.status_code, r.json()["code"]) == (401, None)


# --- 400 ----------------------------------------------------------------------


def errors_of(response) -> list[dict]:
    assert (response.status_code, response.json()["code"]) == (400, "invalidFields")
    return response.json()["errors"]


@pytest.mark.parametrize("body", [{}, {"otro": 1}])
def test_missing_field_is_required(login_as, me, body):
    r = post(login_as(me), body)
    assert errors_of(r) == [{"field": "notificationId", "reason": "required"}]


@pytest.mark.parametrize("raw", ["{", "", "[1]", '"x"'])
def test_unreadable_body_is_required(login_as, me, raw):
    r = login_as(me).post(URL, content=raw, headers={"Content-Type": "application/json"})
    assert errors_of(r) == [{"field": "notificationId", "reason": "required"}]


@pytest.mark.parametrize("value", [None, "1", 1.5, True])
def test_not_an_integer_is_invalid_type(login_as, me, value):
    r = post(login_as(me), {"notificationId": value})
    assert errors_of(r) == [{"field": "notificationId", "reason": "invalidType"}]


@pytest.mark.parametrize("value", [0, -1, 2147483648])
def test_out_of_range_is_out_of_range(login_as, me, value):
    r = post(login_as(me), {"notificationId": value})
    assert errors_of(r) == [{"field": "notificationId", "reason": "outOfRange"}]


# --- 409 ----------------------------------------------------------------------


def test_another_users_notification_is_409_and_changes_nothing(
    login_as, db_session, me, other, add
):
    mine = add(me, 0)
    theirs = add(other, 5)
    r = post(login_as(me), {"notificationId": theirs.id})
    assert (r.status_code, r.json()["code"]) == (409, "notificationNotOwned")
    assert seen_of(db_session, me) == {mine.id: False}
    assert seen_of(db_session, other) == {theirs.id: False}


def test_missing_notification_is_409(login_as, me, add):
    add(me)
    r = post(login_as(me), {"notificationId": 2147483647})
    assert (r.status_code, r.json()["code"]) == (409, "notificationNotOwned")
