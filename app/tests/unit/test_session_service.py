# tests/unit/test_session_service.py
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base  # ajustá al módulo donde está tu Base
from app.models.session import UserSession
from app.services import session_service
from app.services.session_service import SessionService, SESSION_TTL


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def service(db):
    return SessionService(db)


# ---------- create ----------

def test_create_persiste_la_sesion(service, db):
    s = service.create(user_id=1)
    assert db.get(UserSession, s.id) is not None


def test_create_asigna_user_id(service):
    s = service.create(user_id=42)
    assert s.user_id == 42


def test_create_genera_ids_distintos(service):
    ids = {service.create(user_id=1).id for _ in range(20)}
    assert len(ids) == 20


def test_create_id_cabe_en_string_64(service):
    s = service.create(user_id=1)
    assert 0 < len(s.id) <= 64


def test_create_usa_ttl_por_defecto(service):
    s = service.create(user_id=1)
    expires = s.expires_at
    created = s.created_at
    assert expires - created == SESSION_TTL


def test_create_respeta_ttl_custom(service):
    s = service.create(user_id=1, ttl=timedelta(minutes=5))
    assert s.expires_at - s.created_at == timedelta(minutes=5)


# ---------- get_user_id ----------

def test_get_user_id_sesion_valida(service):
    s = service.create(user_id=7)
    assert service.get_user_id(s.id) == 7


def test_get_user_id_sesion_inexistente(service):
    assert service.get_user_id("no-existe") is None


def test_get_user_id_sesion_expirada_devuelve_none(service):
    s = service.create(user_id=1, ttl=timedelta(seconds=-1))
    assert service.get_user_id(s.id) is None


def test_get_user_id_sesion_expirada_se_borra(service, db):
    s = service.create(user_id=1, ttl=timedelta(seconds=-1))
    sid = s.id
    service.get_user_id(sid)
    db.expire_all()
    assert db.get(UserSession, sid) is None


def test_get_user_id_sesion_valida_no_se_borra(service, db):
    s = service.create(user_id=1)
    service.get_user_id(s.id)
    assert db.get(UserSession, s.id) is not None


def test_get_user_id_maneja_expires_at_naive(service, db):
    """SQLite devuelve DateTime sin tz; el servicio debe tratarlo como UTC."""
    s = service.create(user_id=3, ttl=timedelta(hours=1))
    sid = s.id
    db.expire_all()  # fuerza a recargar desde la DB (naive)
    assert service.get_user_id(sid) == 3


def test_get_user_id_usa_utcnow_para_expirar(service, monkeypatch):
    s = service.create(user_id=1, ttl=timedelta(hours=1))
    futuro = datetime.now(timezone.utc) + timedelta(hours=2)
    monkeypatch.setattr(session_service, "_utcnow", lambda: futuro)
    assert service.get_user_id(s.id) is None


def test_get_user_id_justo_en_el_limite_esta_expirada(service, db, monkeypatch):
    s = service.create(user_id=1, ttl=timedelta(hours=1))
    limite = s.expires_at
    if limite.tzinfo is None:
        limite = limite.replace(tzinfo=timezone.utc)
    monkeypatch.setattr(session_service, "_utcnow", lambda: limite)
    assert service.get_user_id(s.id) is None  # el código usa <=


# ---------- delete ----------

def test_delete_elimina_la_sesion(service, db):
    s = service.create(user_id=1)
    sid = s.id
    service.delete(sid)
    assert db.get(UserSession, sid) is None
    assert service.get_user_id(sid) is None


def test_delete_inexistente_no_falla(service):
    service.delete("no-existe")  # no debe lanzar


def test_delete_no_afecta_otras_sesiones(service):
    a = service.create(user_id=1)
    b = service.create(user_id=2)
    service.delete(a.id)
    assert service.get_user_id(b.id) == 2