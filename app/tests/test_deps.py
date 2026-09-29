from datetime import datetime, timedelta, timezone

import pytest

from app.api.deps import get_current_user_id
from app.errors import ApiError
from app.models.session import UserSession
from app.services.session_service import SessionService


def test_valid_session_returns_user_id(db_session):
    session = SessionService(db_session).create(user_id=7)

    assert get_current_user_id(session_id=session.id, db=db_session) == 7


def test_missing_cookie_raises_401(db_session):
    with pytest.raises(ApiError) as exc:
        get_current_user_id(session_id=None, db=db_session)

    assert exc.value.status_code == 401
    assert exc.value.code is None


def test_unknown_session_raises_401(db_session):
    with pytest.raises(ApiError) as exc:
        get_current_user_id(session_id="no-existe", db=db_session)

    assert exc.value.status_code == 401
    assert exc.value.code is None


def test_expired_session_raises_401(db_session):
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
        get_current_user_id(session_id="vencida", db=db_session)

    assert exc.value.status_code == 401


def test_deleted_session_raises_401(db_session):
    service = SessionService(db_session)
    session = service.create(user_id=7)
    service.delete(session.id)

    with pytest.raises(ApiError) as exc:
        get_current_user_id(session_id=session.id, db=db_session)

    assert exc.value.status_code == 401