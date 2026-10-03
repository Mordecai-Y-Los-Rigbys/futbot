import enum
from dataclasses import dataclass

from app.simulation.actions import MoveAction
from app.simulation.geometry import ZERO, Vec


class Team(str, enum.Enum):
    HOME = "home"  # club1: ataca hacia x = FIELD_LENGTH
    AWAY = "away"  # club2: ataca hacia x = 0

    @property
    def opponent(self) -> "Team":
        return Team.AWAY if self is Team.HOME else Team.HOME


class Role(str, enum.Enum):
    DEFENSE = "defense"
    MIDFIELD = "midfield"
    FORWARD = "forward"

    @property
    def number(self) -> int:
        """Número del jugador en cancha: 1 = defensa, 2 = medio, 3 = delantero."""
        return _ROLE_NUMBERS[self]


_ROLE_NUMBERS = {Role.DEFENSE: 1, Role.MIDFIELD: 2, Role.FORWARD: 3}

PlayerKey = tuple[Team, int]

NO_KICK_COOLDOWN = 0          # puede patear desde el primer tick
NOT_REGAIN_BLOCKED = -1       # nunca bloqueado: todos los ticks son > -1
NOT_PROTECTED = -1            # nunca protegida: todos los ticks son > -1


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
    role: Role
    stats: Stats
    position: Vec
    facing: Vec  # hacia donde mira, direccion del ultimo movimiento; ahí lleva la pelota
    move: MoveAction | None = None  # último movimiento pedido
    next_kick_tick: int = NO_KICK_COOLDOWN  # cooldown de agility: puede patear desde este tick
    regain_blocked_until: int = NOT_REGAIN_BLOCKED  # hasta este tick no puede recuperar la pelota despues de patear

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
