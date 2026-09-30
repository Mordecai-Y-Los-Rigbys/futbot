from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_league_service, get_session_service
from app.main import app
from app.repositories.league_abstract import (
    AbstractLeagueRepository,
    LeagueCreatorData,
    LeagueListItemData,
    LeaguePageData,
)
from app.services.league_service import LeagueService


class FakeLeagueRepository(AbstractLeagueRepository):
    """Repositorio en memoria: registra con qué argumentos lo llaman."""

    def __init__(self):
        self.calls = []
        self.page = LeaguePageData(items=[], total=0)

    def list_page(self, name, offset, limit):
        self.calls.append({"name": name, "offset": offset, "limit": limit})
        return self.page


class FakeSessionService:
    """Reemplaza a SessionService: session_id -> user_id, sin base."""

    def __init__(self, sessions: dict[str, int]):
        self.sessions = sessions

    def get_user_id(self, session_id: str) -> int | None:
        return self.sessions.get(session_id)


@pytest.fixture()
def fake_repo():
    return FakeLeagueRepository()


@pytest.fixture()
def service(fake_repo):
    return LeagueService(fake_repo)


@pytest.fixture()
def make_item():
    def _make(
        id=1,
        name="Liga Argentina",
        status="preparation",
        participants_count=1,
        max_participants=8,
        private=False,
        username="mgonzalez",
        club_name="Boca Juniors FC",
        created_at=None,
    ) -> LeagueListItemData:
        return LeagueListItemData(
            id=id,
            name=name,
            creator=LeagueCreatorData(id=7, username=username, club_name=club_name),
            status=status,
            participants_count=participants_count,
            max_participants=max_participants,
            private=private,
            created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    return _make


@pytest.fixture()
def api(fake_repo):
    """Cliente HTTP sin sesión. Se reemplazan el service de sesiones y el de
    ligas, así que no se toca ninguna base (ni se usa get_db)."""
    app.dependency_overrides[get_session_service] = lambda: FakeSessionService(
        {"valid-session": 7}
    )
    app.dependency_overrides[get_league_service] = lambda: LeagueService(fake_repo)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_api(api):
    """Mismo cliente, con cookie de una sesión válida."""
    api.cookies.set("session_id", "valid-session")
    return api