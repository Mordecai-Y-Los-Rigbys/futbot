from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_league_service, get_session_service
from app.main import app
from app.repositories.league_abstract import (
    AbstractLeagueRepository,
    CreateLeagueData,
    LeagueCreatorData,
    LeagueLeaveInfo,
    LeagueDetailData,
    LeagueListItemData,
    LeaguePageData,
)
from app.services.league_service import LeagueService
from app.tests.unit.repo_fakes import FakeBehaviors, FakePlayers, FakeTeams


class FakeLeagueRepository(AbstractLeagueRepository):
    """Repositorio en memoria: registra con qué argumentos lo llaman."""

    def __init__(self):
        self.calls = []
        self.page = LeaguePageData(items=[], total=0)
        self.created: list[CreateLeagueData] = []
        self.durations: dict[int, int] = {}
        self.leave_info: dict[int, LeagueLeaveInfo] = {}
        self.participants: set[tuple[int, int]] = set()
        self.removed: list[tuple[int, int]] = []
        self.details: dict[int, LeagueDetailData] = {}
        self.detail_calls: list[tuple[int, int]] = []

    def list_page(self, name, offset, limit):
        self.calls.append({"name": name, "offset": offset, "limit": limit})
        return self.page

    def create(self, data):
        self.created.append(data)
        return LeagueListItemData(
            id=1,
            name=data.name,
            creator=LeagueCreatorData(
                id=7, username="mgonzalez", club_name="Boca Juniors FC", avatar=1
            ),
            status="preparation",
            participants_count=1,
            max_participants=data.max_participants,
            private=data.private,
            allow_draws=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        
    
    def get_detail(self, league_id, user_id):
        self.detail_calls.append((league_id, user_id))
        return self.details.get(league_id)

    def get_match_duration_minutes(self, league_id):
        return self.durations.get(league_id)
    
    def get_leave_info(self, league_id):
        return self.leave_info.get(league_id)

    def is_participant(self, league_id, user_id):
        return (league_id, user_id) in self.participants

    def remove_participant(self, league_id, user_id):
        self.participants.discard((league_id, user_id))
        self.removed.append((league_id, user_id))

    def get_join_state(self, league_id, user_id):
        raise NotImplementedError

    def join(self, data):
        raise NotImplementedError


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
def fake_teams():
    return FakeTeams()


@pytest.fixture()
def service(fake_repo, fake_players, fake_behaviors):
    return LeagueService(fake_repo, fake_players, fake_behaviors)


@pytest.fixture()
def make_item():
    def _make(
        id=1,
        name="Liga Argentina",
        status="preparation",
        participants_count=1,
        max_participants=8,
        private=False,
        allow_draws=True,
        username="mgonzalez",
        club_name="Boca Juniors FC",
        avatar=1,
        created_at=None,
    ) -> LeagueListItemData:
        return LeagueListItemData(
            id=id,
            name=name,
            creator=LeagueCreatorData(
                id=7, username=username, club_name=club_name, avatar=avatar
            ),
            status=status,
            participants_count=participants_count,
            max_participants=max_participants,
            private=private,
            allow_draws=allow_draws,
            created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    return _make


@pytest.fixture()
def make_detail(make_item):
    def _make(min_participants=3, joined=False, **kwargs) -> LeagueDetailData:
        item = make_item(**kwargs)
        return LeagueDetailData(
            **item.model_dump(), min_participants=min_participants, joined=joined
        )

    return _make


@pytest.fixture()
def auth_api(api):
    """Mismo cliente, con cookie de una sesión válida."""
    api.cookies.set("session_id", "valid-session")
    return api


@pytest.fixture()
def fake_players():
    return FakePlayers()


@pytest.fixture()
def fake_behaviors():
    return FakeBehaviors()


@pytest.fixture()
def api(fake_repo, fake_players, fake_behaviors):
    app.dependency_overrides[get_session_service] = lambda: FakeSessionService({"valid-session": 7})
    app.dependency_overrides[get_league_service] = lambda: LeagueService(
        fake_repo, fake_players, fake_behaviors
    )
    yield TestClient(app)
    app.dependency_overrides.clear()
