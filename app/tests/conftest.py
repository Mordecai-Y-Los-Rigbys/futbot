import os

# Antes de importar cualquier cosa de `app`: app.database exige DATABASE_URL.
# El engine de ese módulo nunca se usa en los tests (se inyecta el de abajo).
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.behavior import Behavior
from app.services.session_service import SessionService
from app.repositories.session_sqlalchemy import SqlAlchemySessionRepository

# Si está definida, los tests corren contra Postgres (una base de tests aparte,
# NUNCA la de desarrollo: el drop_all borra las tablas). Si no, SQLite en memoria.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
# TEST_DATABASE_URL = os.environ.get(
#    "TEST_DATABASE_URL",
#    "postgresql+psycopg2://futbot_user:futbot_pass@db:5432/futbot_test",
# )

if TEST_DATABASE_URL and not TEST_DATABASE_URL.rsplit("/", 1)[-1].endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL debe apuntar a una base *_test")


@pytest.fixture()
def db_session():
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
    else:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,  # una sola conexión compartida: si no, cada una ve una base vacía
        )

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()

# conftest.py
@pytest.fixture()
def make_user(db_session):
    def _make(user_id: int) -> User:
        return ensure_user(db_session, user_id)
    return _make

@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def ensure_user(db_session, user_id: int) -> User:
    """
    Crea el usuario si no existe. SQLite no hace cumplir las FK, pero Postgres sí:
    Util para tests varios.
    """
    user = db_session.get(User, user_id)
    if user is None:
        user = User(
            id=user_id,
            username=f"user{user_id}",
            email=f"user{user_id}@test.com",
            password_hash="x",
            club_name=f"club{user_id}",
            avatar=1,
        )
        db_session.add(user)
        db_session.commit()
    return user

def pytest_collection_modifyitems(config, items):
    if not os.environ.get("TEST_DATABASE_URL"):
        skip = pytest.mark.skip(reason="requiere TEST_DATABASE_URL")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)


@pytest.fixture()
def auth_cookies(db_session, session_service):
    def _make(user_id: int) -> dict:
        ensure_user(db_session, user_id)
        repo = SqlAlchemySessionRepository(db_session)
        session = SessionService(repo).create(user_id)
        return {"session_id": session.id}

    return _make
  
@pytest.fixture
def session_service(db_session):
    return SessionService(SqlAlchemySessionRepository(db_session))

@pytest.fixture()
def make_behaviors(db_session):
    """make_behaviors(user_id, names) -> list[Behavior], en orden de creación."""

    def _make(user_id: int, names, code: str = "def behave(): pass") -> list[Behavior]:
        ensure_user(db_session, user_id)
        created = []
        for name in names:
            b = Behavior(user_id=user_id, name=name, code=code)
            db_session.add(b)
            db_session.commit()  # uno a uno: ids crecientes en el orden dado
            db_session.refresh(b)
            created.append(b)
        return created

    return _make
