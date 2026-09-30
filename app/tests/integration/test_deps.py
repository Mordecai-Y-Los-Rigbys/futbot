from datetime import datetime, timedelta, timezone

import pytest

from app.api.deps import get_current_user_id
from app.errors import ApiError
from app.models.session import UserSession
from app.repositories.session_sqlalchemy import SqlAlchemySessionRepository
from app.services.session_service import SessionService

pytestmark = pytest.mark.integration


@pytest.fixture
def service(db_session):
    return SessionService(SqlAlchemySessionRepository(db_session))


def test_valid_session_returns_user_id(service, make_user):
    make_user(7)
    session = service.create(user_id=7)

    assert get_current_user_id(session_id=session.id, service=service) == 7


def test_missing_cookie_raises_401(service):
    with pytest.raises(ApiError) as exc:
        get_current_user_id(session_id=None, service=service)

    assert exc.value.status_code == 401
    assert exc.value.code is None


def test_unknown_session_raises_401(service):
    with pytest.raises(ApiError) as exc:
        get_current_user_id(session_id="no-existe", service=service)

    assert exc.value.status_code == 401
    assert exc.value.code is None


def test_expired_session_raises_401(service, db_session, make_user):
    make_user(7)
    now = datetime.now(timezone.utc)
    db_session.add(
        UserSession(
            id="vencida",
            user_id=7,
            created_at=now - timedelta(days=8),
            expires_at=now - timedelta(days=1),
        )
    )
    db_session.commit()

    with pytest.raises(ApiError) as exc:
        get_current_user_id(session_id="vencida", service=service)

    assert exc.value.status_code == 401
    assert exc.value.code is None


def test_deleted_session_raises_401(service, make_user):
    make_user(7)
    session = service.create(user_id=7)
    service.delete(session.id)

    with pytest.raises(ApiError) as exc:
        get_current_user_id(session_id=session.id, service=service)

    assert exc.value.status_code == 401
    assert exc.value.code is None
