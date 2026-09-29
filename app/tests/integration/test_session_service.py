# app/tests/integration/test_session_service_pg.py
from datetime import timedelta

import pytest

from app.models.session import UserSession
from app.models.user import User
from app.services.session_service import SessionService

pytestmark = pytest.mark.integration


@pytest.fixture
def user(db_session):
    u = User(
        username="pguser", email="pg@test.com", password_hash="x",
        club_name="club", avatar="a",
    )
    db_session.add(u)
    db_session.commit()
    return u


def test_flujo_completo_con_fk_real(db_session, user):
    svc = SessionService(db_session)
    s = svc.create(user_id=user.id)
    assert svc.get_user_id(s.id) == user.id
    svc.delete(s.id)
    assert svc.get_user_id(s.id) is None


def test_sesion_expirada_con_expires_at_aware(db_session, user):
    svc = SessionService(db_session)
    s = svc.create(user_id=user.id, ttl=timedelta(seconds=-1))
    db_session.expire_all()
    assert svc.get_user_id(s.id) is None


def test_no_se_puede_crear_sesion_de_usuario_inexistente(db_session):
    from sqlalchemy.exc import IntegrityError
    svc = SessionService(db_session)
    with pytest.raises(IntegrityError):
        svc.create(user_id=999999)
    db_session.rollback()