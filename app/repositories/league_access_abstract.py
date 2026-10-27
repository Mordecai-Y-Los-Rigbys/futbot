from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class LeagueAccessInfo:
    id: int
    creator_id: int
    private: bool
    password: str | None = field(repr=False)


class LeagueAccessRepository(Protocol):
    def get_league(self, league_id: int) -> LeagueAccessInfo | None: ...

    def is_participant(self, league_id: int, user_id: int) -> bool: ...

    def is_unlocked(self, session_id: str, league_id: int) -> bool: ...

    def unlock(self, session_id: str, league_id: int, *, commit: bool = True) -> None:
        """Idempotente. commit=False permite incluirlo en la transacción de inscripción."""
        ...
