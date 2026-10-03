"""Física del partido.

`step(estado, acciones)` no modifica el estado recibido y
siempre devuelve el mismo resultado para la misma entrada gracias a la semilla.

Orden de un tick:
    1. Movimiento de los jugadores (speed).
    2. Choques entre jugadores (strength).
    3. Pelota: acompaña al poseedor, o avanza, se frena, rebota y puede ser gol.
    4. Posesión (control, strength, protección).
    5. Patadas (power, agility).
"""

import copy
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.simulation import constants as C
from app.simulation.actions import GoTo, Kick, KickAction, MoveInDirection, PlayerActions
from app.simulation.geometry import ZERO, Vec, clamp
from app.simulation.state import (
    NO_KICK_COOLDOWN,
    NOT_REGAIN_BLOCKED,
    NOT_PROTECTED,
    BallState,
    Goal,
    MatchState,
    PlayerKey,
    PlayerState,
    Stats,
    StepResult,
    Team,
)
from app.domain.team_member import MemberRole

# --- Stats -> física ------------------------------------------------------------


def player_speed(speed: int) -> float:
    """Velocidad de movimiento en u/s."""
    return C.PLAYER_BASE_SPEED + speed * C.PLAYER_SPEED_PER_POINT


def max_kick_speed(power: int) -> float:
    """Velocidad de la pelota con una patada a fuerza máxima, en u/s."""
    return C.KICK_BASE_SPEED + power * C.KICK_SPEED_PER_POINT


def reach(control: int) -> float:
    """Distancia máxima a la que puede controlar la pelota."""
    return C.PLAYER_RADIUS + C.BALL_RADIUS + control * C.REACH_PER_CONTROL_POINT


def kick_cooldown_ticks(agility: int) -> int:
    """Ticks entre dos patadas del mismo jugador."""
    return round(C.KICK_COOLDOWN_BASE_TICKS - agility * C.KICK_COOLDOWN_TICKS_PER_POINT)


# --- Estado inicial ---------------------------------------------------------------


@dataclass(frozen=True)
class PlayerSetup:
    player_id: int
    role: MemberRole
    stats: Stats


def _absolute(team: Team, x: float, y: float) -> Vec:
    """Coordenadas relativas al equipo -> absolutas (el visitante se espeja)."""
    if team is Team.HOME:
        return Vec(x, y)
    return Vec(C.FIELD_LENGTH - x, C.FIELD_WIDTH - y)


def _attack_direction(team: Team) -> Vec:
    return Vec(1.0, 0.0) if team is Team.HOME else Vec(-1.0, 0.0)


def create_initial_state(
    home: Sequence[PlayerSetup], away: Sequence[PlayerSetup], seed: int
) -> MatchState:
    """Estado al arrancar el partido: titulares en sus posiciones por rol y la
    pelota libre en el centro."""
    players = []
    for team, setups in ((Team.HOME, home), (Team.AWAY, away)):
        if sorted(s.role.number for s in setups) != sorted(r.number for r in C.STARTER_ROLES):
            raise ValueError(f"{team.value}: se necesita un defensa, un medio y un delantero")
        for setup in sorted(setups, key=lambda s: s.role.number):
            players.append(
                PlayerState(
                    player_id=setup.player_id,
                    team=team,
                    role=setup.role,
                    stats=setup.stats,
                    position=ZERO,
                    facing=_attack_direction(team),
                )
            )
    state = MatchState(players=players, ball=BallState(position=ZERO), seed=seed)
    return reset_positions(state)


def reset_positions(state: MatchState) -> MatchState:
    """Nuevo estado con todos en sus posiciones iniciales y la pelota libre y
    quieta en el centro (arranque y reacomodo después de un gol). Conserva el
    tick."""
    new = copy.deepcopy(state)
    for player in new.players:
        player.position = _absolute(player.team, *C.INITIAL_POSITIONS[player.number])
        player.facing = _attack_direction(player.team)
        player.move = None
        player.next_kick_tick = NO_KICK_COOLDOWN
        player.regain_blocked_until = NOT_REGAIN_BLOCKED
    new.ball = BallState(position=Vec(*C.KICKOFF_BALL_POSITION))
    return new


# --- Tick -------------------------------------------------------------------------------


def step(
    state: MatchState, actions: Mapping[PlayerKey, PlayerActions] | None = None
) -> StepResult:
    """Avanza un tick. `actions` usa coordenadas absolutas."""
    actions = actions or {}
    state_copy = copy.deepcopy(state)
    state_copy.tick += 1

    #Mover jugadores y resolver choques
    for player in state_copy.players:
        requested = actions.get(player.key)
        if requested is not None and requested.move is not None:
            player.move = requested.move
        _move_player(player)

    _resolve_collisions(state_copy.players)

    # Actualizar pelota, chequear gol y posesión
    goal = _update_ball(state_copy)
    if goal is not None:
        return StepResult(state_copy, (goal,))

    _resolve_possession(state_copy)
    # Patear la pelota
    for player in state_copy.players:
        requested = actions.get(player.key)
        if requested is not None and requested.kick is not None:
            _kick(state_copy, player, requested.kick)

    return StepResult(state_copy)


# --- Movimiento ------------------------------------------------------------------------

# limita la posicion de un jugador al campo
def _clamp_player(vector: Vec) -> Vec:
    r = C.PLAYER_RADIUS
    return Vec(clamp(vector.x, r, C.FIELD_LENGTH - r), clamp(vector.y, r, C.FIELD_WIDTH - r))

# limita un punto del espacio al campo
def _clamp_to_field(vector: Vec) -> Vec:
    return Vec(clamp(vector.x, 0.0, C.FIELD_LENGTH), clamp(vector.y, 0.0, C.FIELD_WIDTH))


def _move_player(player: PlayerState) -> None:
    max_step = player_speed(player.stats.speed) * C.SECONDS_PER_TICK 
    if isinstance(player.move, MoveInDirection):
        delta = Vec(player.move.dx, player.move.dy).normalized() * max_step # desplazamiento en este tick
    elif isinstance(player.move, GoTo):
        to_target = _clamp_player(Vec(player.move.x, player.move.y)) - player.position
        distance = to_target.length()
        if distance == 0:
            return
        delta = to_target * min(1.0, max_step / distance)
    else:
        return

    if delta.length() == 0:
        return
    new_position = _clamp_player(player.position + delta)
    moved = new_position - player.position
    if moved.length() > 0:
        player.facing = moved.normalized()
    player.position = new_position


# --- Choques -------------------------------------------------------------------------------


def _resolve_collisions(players: list[PlayerState]) -> None:
    """Separa a los jugadores superpuestos. El desplazamiento se reparte en
    proporción inversa a strength: el más fuerte se mueve menos. Es un
    forcejeo, no un impulso: no deja velocidad residual."""
    
    # queda ordenado para que el resultado sea siempre el mismo
    ordered = sorted(players, key=lambda p: (p.team.value, p.number)) 
    
    for _ in range(C.COLLISION_PASSES):
        any_separated = False
        for i, player_a in enumerate(ordered):
            for player_b in ordered[i + 1 :]:
                if _separate(player_a, player_b):
                    any_separated = True
        if not any_separated:
            return

def _separate(player_a: PlayerState, player_b: PlayerState) -> bool:
    """Si los dos jugadores se superponen, los separa: cada uno empuja al otro
    en proporción a su propia fuerza. Devuelve True si tuvo que separarlos."""
    min_distance = 2 * C.PLAYER_RADIUS # si los centros estan mas cerca hay colision
    between = player_b.position - player_a.position
    distance = between.length()
    if distance >= min_distance:
        return False

    push_direction = between.normalized() if distance > 0 else Vec(1.0, 0.0)
    overlap = min_distance - distance # cuánto se superponen
    total = player_a.stats.strength + player_b.stats.strength
    push_by_a = push_direction * (overlap * player_a.stats.strength / total)
    push_by_b = push_direction * (overlap * player_b.stats.strength / total)
    player_a.position = _clamp_player(player_a.position - push_by_b)
    player_b.position = _clamp_player(player_b.position + push_by_a)
    return True

# --- Pelota ----------------------------------------------------------------------------------


# chequea si la pelota se sale del campo y la devuelve a la cancha
def _clamp_ball(vector: Vec) -> Vec:
    r = C.BALL_RADIUS
    return Vec(clamp(vector.x, r, C.FIELD_LENGTH - r), clamp(vector.y, r, C.FIELD_WIDTH - r))


def _on_goal_line(y: float) -> bool:
    """True si la altura 'y' queda entre los palos."""
    return C.GOAL_Y_MIN <= y <= C.GOAL_Y_MAX

def _goal_crossing(old: Vec, new: Vec) -> Goal | None:
    """Goal si la pelota, al ir de old a new, cruzó una línea de fondo entre
    los palos. Si no, None."""
    for line, scorer in ((0.0, Team.AWAY), (C.FIELD_LENGTH, Team.HOME)):
        crossed = (new.x - line) * (old.x - line) <= 0 and new.x != old.x
        if not crossed:
            continue
        # Fracción del recorrido en la que tocó la línea, y la altura en ese punto.
        t = (line - old.x) / (new.x - old.x)
        y_at_crossing = old.y + (new.y - old.y) * t
        if _on_goal_line(y_at_crossing):
            return Goal(scoring_team=scorer)
    return None

def _update_ball(state: MatchState) -> Goal | None:
    ball = state.ball
    if ball.owner is None and ball.velocity == ZERO:
        return None  # libre y quieta: nada que hacer

    # A dónde va la pelota en este tick.
    old_position = ball.position
    if ball.owner is not None:
        # Llevada: se acerca al frente del jugador a BALL_CARRY_SPEED; cuando
        # llega, queda pegada.
        owner = state.player(ball.owner)
        offset = C.PLAYER_RADIUS + C.BALL_RADIUS
        carry_spot = owner.position + owner.facing * offset
        to_carry_spot = carry_spot - old_position
        max_step = C.BALL_CARRY_SPEED * C.SECONDS_PER_TICK
        if to_carry_spot.length() <= max_step:
            new_position = carry_spot
        else:
            new_position = old_position + to_carry_spot.normalized() * max_step
    else:
        # Libre: avanza según su velocidad.
        new_position = old_position + ball.velocity * C.SECONDS_PER_TICK

    # Gol: llevada o pateada, si cruza la línea entre los palos.
    goal = _goal_crossing(old_position, new_position)
    if goal is not None:
        ball.position = new_position  # adentro del arco
        ball.velocity = ZERO
        ball.owner = None
        return goal

    # Llevada sin gol: queda dentro de la cancha.
    if ball.owner is not None:
        ball.position = _clamp_ball(new_position)
        return None

    # Libre sin gol: rebote en las paredes. Frente al arco no hay pared, así que normalmente no rebota ahí. 
    # Pero si la pelota ya pasó la línea de fondo y no fue gol, es porque cruzó por afuera
    # de los palos (chocó la pared): en ese caso rebota igual.
    
    # Las paredes estan a un radio del borde de la cancha, así que la pelota no puede ir más allá de eso.
    wall_min_x = C.BALL_RADIUS
    wall_max_x = C.FIELD_LENGTH - C.BALL_RADIUS
    wall_min_y = C.BALL_RADIUS
    wall_max_y = C.FIELD_WIDTH - C.BALL_RADIUS
    
    x, y = new_position.x, new_position.y
    velocity_x, velocity_y  = ball.velocity.x, ball.velocity.y

    # Rebotar = reflejar la posición del otro lado de la pared (lo que se pasó,
    # vuelve hacia adentro) e invertir la velocidad, perdiendo un poco.
    if x < wall_min_x and (x < 0 or not _on_goal_line(y)):
        x = 2 * wall_min_x - x
        velocity_x = -velocity_x * C.WALL_RESTITUTION
    elif x > wall_max_x and (x > C.FIELD_LENGTH or not _on_goal_line(y)):
        x =  2 * (wall_max_x) - x
        velocity_x = -velocity_x * C.WALL_RESTITUTION

    if y < wall_min_y:
        y = 2 * wall_min_y - y
        velocity_y = -velocity_y * C.WALL_RESTITUTION
    elif y > wall_max_y:
        y = 2 * wall_max_y - y
        velocity_y = -velocity_y * C.WALL_RESTITUTION

    new_velocity = Vec(velocity_x, velocity_y) * C.BALL_FRICTION_PER_TICK
    if new_velocity.length() < C.BALL_MIN_SPEED:
        new_velocity = ZERO
    ball.position = Vec(x, y)
    ball.velocity = new_velocity
    return None


# --- Posesión ------------------------------------------------------------------------------


def _resolve_possession(state: MatchState) -> None:
    """Decide quién tiene la pelota al final de cada tick."""
    ball = state.ball
    if ball.owner is not None and state.tick <= ball.protected_until:
        return

    # Son candidatos los que esten al alcance y no tengan bloqueada la recuperación
    candidates = [ p for p in state.players
        if state.tick > p.regain_blocked_until and 
        (p.position - ball.position).length() <= reach(p.stats.control)
    ]
    if not candidates:
        return

    strongest = max(p.stats.strength for p in candidates)
    candidates = [p for p in candidates if p.stats.strength == strongest] 
    # Si hay varios con la misma fuerza, gana el que esté más cerca de la pelota.
    closest = min((p.position - ball.position).length() for p in candidates)
    candidates = [
        p
        for p in candidates
        if (p.position - ball.position).length() - closest <= C.DISTANCE_EPSILON
    ]
    
    candidates.sort(key=lambda p: (p.team.value, p.number))
    if len(candidates) == 1:
        winner = candidates[0]
    else:
        # Empate exacto: al azar, pero reproducible (semilla del partido + tick).
        winner = random.Random(f"{state.seed}:{state.tick}").choice(candidates)

    if winner.key != ball.owner:
        ball.owner = winner.key
        ball.protected_until = state.tick + C.POSSESSION_PROTECTION_TICKS
        ball.velocity = ZERO


# --- Patadas --------------------------------------------------------------------------------


def _kick(state: MatchState, player: PlayerState, kick: KickAction) -> None:
    """Se llama al final del tick para cada jugador que pidió patear. Hace cinco cosas:

    1. ¿Puede patear?         → si no tiene la pelota o está en cooldown, no hace nada
    2. ¿Qué es "adelante"?    → la línea jugador → pelota
    3. ¿Hacia dónde sale?     → adelante (kick) o hacia un punto (kick_to)
    4. ¿Con qué velocidad?    → force × power
    5. Soltar la pelota       → velocidad, sin dueño, cooldown y bloqueo"""
    
    ball = state.ball
    if ball.owner != player.key or state.tick < player.next_kick_tick:
        return

    forward = (ball.position - player.position).normalized()
    if forward == ZERO:
        forward = player.facing

    if isinstance(kick, Kick):
        direction = forward
    else:
        target = _clamp_to_field(Vec(kick.x, kick.y))
        direction = (target - ball.position).normalized()
        if direction == ZERO:
            direction = forward
        elif direction.dot(forward) < 0:
            # El destino queda detrás: se patea hacia el lateral (±90°) más cercano.
            side = forward.perpendicular()
            direction = side if direction.dot(side) >= 0 else -side

    force = clamp(kick.force, C.MIN_KICK_FORCE, C.MAX_KICK_FORCE)
    speed = force / C.MAX_KICK_FORCE * max_kick_speed(player.stats.power)

    ball.velocity = direction * speed
    ball.owner = None
    ball.protected_until = NOT_PROTECTED
    player.next_kick_tick = state.tick + kick_cooldown_ticks(player.stats.agility)
    player.regain_blocked_until = state.tick + C.KICKER_REGAIN_BLOCK_TICKS
