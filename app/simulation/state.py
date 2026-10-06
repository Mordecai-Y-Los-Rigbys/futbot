import enum
from dataclasses import dataclass

from app.simulation.actions import MoveAction
from app.simulation.constants import NO_KICK_COOLDOWN, NOT_REGAIN_BLOCKED, NOT_PROTECTED
from app.simulation.geometry import ZERO, Vec
from app.domain.team_member import MemberRole


class Team(str, enum.Enum):
    HOME = "home"  # club1: ataca hacia x = FIELD_LENGTH
    AWAY = "away"  # club2: ataca hacia x = 0

    @property
    def opponent(self) -> "Team":
        return Team.AWAY if self is Team.HOME else Team.HOME


PlayerKey = tuple[Team, int]


@dataclass(frozen=True)
class Stats:
    power: int
    agility: int
    control: int
    strength: int
    speed: int


@dataclass
class PlayerState:
    player_id: int
    team: Team
    role: MemberRole
    stats: Stats
    position: Vec
    facing: Vec  # hacia donde mira, direccion del ultimo movimiento; ahí lleva la pelota
    move: MoveAction | None = None  # último movimiento pedido
    next_kick_tick: int = NO_KICK_COOLDOWN  # cooldown de agility: puede patear desde este tick
    regain_blocked_until: int = (
        NOT_REGAIN_BLOCKED  # hasta este tick no puede recuperar la pelota despues de patear
    )

    @property
    def number(self) -> int:
        return self.role.number

    @property
    def key(self) -> PlayerKey:
        return (self.team, self.number)


@dataclass
class BallState:
    position: Vec
    velocity: Vec = ZERO
    owner: PlayerKey | None = None
    protected_until: int = NOT_PROTECTED


@dataclass
class MatchState:
    players: list[PlayerState]
    ball: BallState
    seed: int  # semilla del partido: desempates exactos reproducibles
    tick: int = 0

    def player(self, key: PlayerKey) -> PlayerState:
        for p in self.players:
            if p.key == key:
                return p
        raise KeyError(key)


@dataclass(frozen=True)
class Goal:
    """Evento: `scoring_team` hizo un gol en este tick."""

    scoring_team: Team


@dataclass(frozen=True)
class StepResult:
    state: MatchState
    events: tuple[Goal, ...] = ()
