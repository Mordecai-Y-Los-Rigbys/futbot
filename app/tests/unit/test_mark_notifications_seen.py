from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_notification_service, get_session_service
from app.errors import ApiError, ValidationApiError
from app.main import app
from app.services.league_validation import INVALID_JSON
from app.services.notification_service import NotificationService
from app.services.session_service import SessionService
from app.tests.unit.notification_fakes import FakeNotifications, match_notification

USER_ID = 7
OTHER_ID = 8
URL = "/notifications/seen"


class SpyNotifier:
    def __init__(self):
        self.calls: list[list[int]] = []

    def notifications_changed(self, user_ids):
        self.calls.append(list(user_ids))


@pytest.fixture()
def notifications():
    repo = FakeNotifications()
    for i, minute in ((1, 0), (2, 5), (3, 10)):
        repo.add(USER_ID, match_notification(i, minute=minute))
    repo.add(OTHER_ID, match_notification(4, minute=15))
    return repo


@pytest.fixture()
def notifier():
    return SpyNotifier()


@pytest.fixture()
def service(notifications, notifier):
    return NotificationService(notifications, notifier)


def seen_by_id(notifications, user_id) -> dict[int, bool]:
    return {n.id: n.seen for n in notifications.by_user[user_id]}


def validation_errors(body, service) -> list[dict]:
    with pytest.raises(ValidationApiError) as exc:
        service.mark_seen(USER_ID, body)
    return exc.value.errors


# --- service: marcado ---------------------------------------------------------


def test_marks_the_given_one_and_the_older_ones(service, notifications):
    service.mark_seen(USER_ID, {"notificationId": 2})
    assert seen_by_id(notifications, USER_ID) == {1: True, 2: True, 3: False}


def test_does_not_touch_other_users(service, notifications):
    service.mark_seen(USER_ID, {"notificationId": 3})
    assert seen_by_id(notifications, OTHER_ID) == {4: False}


def test_repeating_it_is_idempotent(service, notifications, notifier):
    service.mark_seen(USER_ID, {"notificationId": 2})
    service.mark_seen(USER_ID, {"notificationId": 2})
    assert seen_by_id(notifications, USER_ID) == {1: True, 2: True, 3: False}
    assert notifier.calls == [[USER_ID], [USER_ID]]


def test_notifies_only_the_user(service, notifier):
    service.mark_seen(USER_ID, {"notificationId": 1})
    assert notifier.calls == [[USER_ID]]


def test_extra_fields_are_ignored(service, notifications):
    service.mark_seen(USER_ID, {"notificationId": 1, "otro": "x"})
    assert seen_by_id(notifications, USER_ID)[1] is True


# --- service: 400 -------------------------------------------------------------


@pytest.mark.parametrize("body", [None, INVALID_JSON, [], [1], "x", 5, {}])
def test_missing_field_or_unreadable_body_is_required(service, body):
    assert validation_errors(body, service) == [{"field": "notificationId", "reason": "required"}]


@pytest.mark.parametrize("value", [None, "1", 1.0, 1.5, True, [1], {"id": 1}])
def test_not_an_integer_is_invalid_type(service, value):
    errors = validation_errors({"notificationId": value}, service)
    assert errors == [{"field": "notificationId", "reason": "invalidType"}]


@pytest.mark.parametrize("value", [0, -1, 2147483648])
def test_out_of_range_is_out_of_range(service, value):
    errors = validation_errors({"notificationId": value}, service)
    assert errors == [{"field": "notificationId", "reason": "outOfRange"}]


def test_a_400_changes_nothing_and_notifies_nothing(service, notifications, notifier):
    validation_errors({"notificationId": 0}, service)
    assert not any(seen_by_id(notifications, USER_ID).values())
    assert notifier.calls == []


# --- service: 409 -------------------------------------------------------------


@pytest.mark.parametrize("notification_id", [4, 999])
def test_another_users_or_missing_notification_is_409(
    service, notifications, notifier, notification_id
):
    with pytest.raises(ApiError) as exc:
        service.mark_seen(USER_ID, {"notificationId": notification_id})
    assert (exc.value.status_code, exc.value.code) == (409, "notificationNotOwned")
    assert not any(seen_by_id(notifications, USER_ID).values())
    assert seen_by_id(notifications, OTHER_ID) == {4: False}
    assert notifier.calls == []


def test_400_is_evaluated_before_409(service):
    errors = validation_errors({"notificationId": "999"}, service)
    assert errors == [{"field": "notificationId", "reason": "invalidType"}]


# --- endpoint -----------------------------------------------------------------


@pytest.fixture()
def mocked_service():
    return create_autospec(NotificationService, instance=True)


@pytest.fixture()
def client(mocked_service):
    sessions = create_autospec(SessionService, instance=True)
    sessions.get_user_id.side_effect = lambda sid: USER_ID if sid == "ok" else None
    app.dependency_overrides[get_session_service] = lambda: sessions
    app.dependency_overrides[get_notification_service] = lambda: mocked_service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_valid_request_is_204_without_body(client, mocked_service):
    client.cookies.set("session_id", "ok")
    r = client.post(URL, json={"notificationId": 3})
    assert r.status_code == 204 and r.content == b""
    mocked_service.mark_seen.assert_called_once_with(USER_ID, {"notificationId": 3})


@pytest.mark.parametrize("session", [None, "no-existe"])
@pytest.mark.parametrize("body", [{"notificationId": 3}, {"notificationId": "x"}, None])
def test_no_valid_session_is_401_even_with_an_invalid_body(client, mocked_service, session, body):
    if session:
        client.cookies.set("session_id", session)
    r = client.post(URL, json=body)
    assert r.status_code == 401 and r.json()["code"] is None
    mocked_service.mark_seen.assert_not_called()


def test_unparseable_body_reaches_the_service_as_invalid_json(client, mocked_service):
    client.cookies.set("session_id", "ok")
    client.post(URL, content="{", headers={"Content-Type": "application/json"})
    mocked_service.mark_seen.assert_called_once_with(USER_ID, INVALID_JSON)


def test_empty_body_reaches_the_service_as_none(client, mocked_service):
    client.cookies.set("session_id", "ok")
    client.post(URL)
    mocked_service.mark_seen.assert_called_once_with(USER_ID, None)


@pytest.mark.parametrize(
    "error, status, code",
    [
        (
            ValidationApiError([{"field": "notificationId", "reason": "required"}]),
            400,
            "invalidFields",
        ),
        (ApiError(409, "notificationNotOwned", "x"), 409, "notificationNotOwned"),
    ],
)
def test_service_errors_keep_their_status_and_code(client, mocked_service, error, status, code):
    client.cookies.set("session_id", "ok")
    mocked_service.mark_seen.side_effect = error
    r = client.post(URL, json={"notificationId": 3})
    assert (r.status_code, r.json()["code"]) == (status, code)


def test_the_400_lists_the_field_and_the_reason(client, mocked_service):
    client.cookies.set("session_id", "ok")
    mocked_service.mark_seen.side_effect = ValidationApiError(
        [{"field": "notificationId", "reason": "outOfRange"}]
    )
    body = client.post(URL, json={"notificationId": 0}).json()
    assert body["errors"] == [{"field": "notificationId", "reason": "outOfRange"}]
