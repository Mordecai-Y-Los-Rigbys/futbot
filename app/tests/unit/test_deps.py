from unittest.mock import create_autospec

import pytest
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import get_current_user_id, get_session_service
from app.errors import ApiError
from app.services.session_service import SessionService


@pytest.fixture
def service():
    return create_autospec(SessionService, instance=True)


# ---------- get_current_user_id ----------

def test_valid_session_returns_user_id(service):
    service.get_user_id.return_value = 7

    assert get_current_user_id(session_id="sid", service=service) == 7
    service.get_user_id.assert_called_once_with("sid")


@pytest.mark.parametrize("cookie", [None, ""])
def test_missing_cookie_raises_401(service, cookie):
    with pytest.raises(ApiError) as exc:
        get_current_user_id(session_id=cookie, service=service)

    assert exc.value.status_code == 401
    assert exc.value.code is None


@pytest.mark.parametrize("cookie", [None, ""])
def test_missing_cookie_does_not_query_the_service(service, cookie):
    with pytest.raises(ApiError):
        get_current_user_id(session_id=cookie, service=service)

    service.get_user_id.assert_not_called()


def test_unknown_or_expired_session_raises_401(service):
    # the service returns None both for nonexistent and expired sessions
    service.get_user_id.return_value = None

    with pytest.raises(ApiError) as exc:
        get_current_user_id(session_id="sid", service=service)

    assert exc.value.status_code == 401
    assert exc.value.code is None
    service.get_user_id.assert_called_once_with("sid")


def test_user_id_zero_is_not_treated_as_missing(service):
    # `is None` check: a falsy but valid id must not produce 401
    service.get_user_id.return_value = 0

    assert get_current_user_id(session_id="sid", service=service) == 0