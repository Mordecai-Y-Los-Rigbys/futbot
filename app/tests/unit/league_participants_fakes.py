from datetime import datetime, timedelta, timezone

from app.domain.league import LeagueStatus
from app.repositories.league_access_abstract import LeagueAccessInfo
from app.repositories.league_participants_abstract import LeagueParticipantsState, ParticipantData
from app.repositories.session_abstract import SessionData

ORIGIN = "http://localhost:5173"
CREATOR_ID = 7


def far_future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=1)


def participant(user_id: int) -> ParticipantData:
    return ParticipantData(
        id=user_id, username=f"user{user_id}", club_name=f"club{user_id}", avatar=1
    )


class FakeSessions:
    """session_id -> SessionData, sin base."""

    def __init__(self):
        self.sessions: dict[str, SessionData] = {}

    def add(self, session_id: str, user_id: int, expires_at: datetime | None = None):
        now = datetime.now(timezone.utc)
        self.sessions[session_id] = SessionData(
            id=session_id, user_id=user_id, created_at=now, expires_at=expires_at or far_future()
        )

    def get_valid(self, session_id: str) -> SessionData | None:
        return self.sessions.get(session_id)


class FakeLeagues:
    """Hace de repositorio de acceso y de participantes a la vez.

    `members` incluye al creador. Cambiar el estado o los participantes y
    llamar al notifier simula lo que hacen los endpoints REST.
    """

    def __init__(self):
        self.leagues: dict[int, dict] = {}
        self.unlocks: set[tuple[str, int]] = set()
        self.state_reads: list[int] = []

    def add(
        self, league_id=1, creator_id=CREATOR_ID, private=False, status=LeagueStatus.preparation
    ):
        self.leagues[league_id] = {
            "creator_id": creator_id,
            "private": private,
            "status": LeagueStatus(status),
            "members": [creator_id],
        }

    def join(self, league_id: int, user_id: int):
        self.leagues[league_id]["members"].append(user_id)

    def leave(self, league_id: int, user_id: int):
        self.leagues[league_id]["members"].remove(user_id)

    def set_status(self, league_id: int, status: LeagueStatus):
        self.leagues[league_id]["status"] = LeagueStatus(status)

    # --- LeagueAccessRepository ---
    def get_league(self, league_id):
        league = self.leagues.get(league_id)
        if league is None:
            return None
        password = "secret" if league["private"] else None
        return LeagueAccessInfo(league_id, league["creator_id"], league["private"], password)

    def is_participant(self, league_id, user_id):
        return user_id in self.leagues.get(league_id, {}).get("members", [])

    def is_unlocked(self, session_id, league_id):
        return (session_id, league_id) in self.unlocks

    def unlock(self, session_id, league_id):
        self.unlocks.add((session_id, league_id))

    # --- LeagueParticipantsRepository ---
    def get_status(self, league_id):
        league = self.leagues.get(league_id)
        return None if league is None else league["status"]

    def get_state(self, league_id):
        self.state_reads.append(league_id)
        league = self.leagues.get(league_id)
        if league is None:
            return None
        return LeagueParticipantsState(
            status=league["status"],
            participants=[participant(uid) for uid in league["members"]],
        )
