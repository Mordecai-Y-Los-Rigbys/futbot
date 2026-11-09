"""Reglas de la prueba de un comportamiento: un 3 contra 3 sin pausas."""

import pytest

from app.domain.team_member import MemberRole
from app.repositories.team_abstract import StarterData
from app.services.behavior_test_rules import build_test_session
from app.simulation import constants as C
from app.simulation.behaviors.default_behaviors import FORWARD_CODE
from app.simulation.geometry import Vec
from app.simulation.match_rules import Event, Phase
from app.simulation.state import Team

COUNTDOWN_TICKS = 3 * C.TICKS_PER_SECOND
FIELD_CENTER = Vec(50.0, 30.0)
IDLE = "pass"
# Se va a una esquina de su propio arco: deja libre el camino hacia ese arco.
OUT_OF_THE_WAY = "go_to(0, 0)"


def starter(player_id, role, code=IDLE):
    return StarterData(
        player_id=player_id,
        name=f"Jugador {player_id}",
        role=role,
        power=60,
        agility=60,
        control=60,
        strength=60,
        speed=60,
        behavior_code=code,
    )


def club(first_id, codes=None):
    """Un club con un titular por rol. `codes` cambia el behavior de algún rol."""
    codes = codes or {}
    return [
        starter(first_id + role.number, role, codes.get(role, IDLE)) for role in C.STARTER_ROLES
    ]


def play(club_1, club_2):
    """Corre la prueba completa y devuelve todos sus ticks."""
    session = build_test_session(club_1, club_2, seed=1)
    ticks = []
    while not session.finished:
        ticks.append(session.advance())
    return ticks


def positions(tick):
    return {player.key: player.position for player in tick.state.players}


# --- countdown ----------------------------------------------------------------


def test_countdown_of_3_seconds_with_nobody_moving():
    session = build_test_session(club(0, {MemberRole.forward: "go_to(0, 0)"}), club(10), seed=1)
    ticks = [session.advance() for _ in range(COUNTDOWN_TICKS + 1)]
    countdown, first_play = ticks[:COUNTDOWN_TICKS], ticks[COUNTDOWN_TICKS]

    assert (ticks[0].phase, ticks[0].event) == (Phase.COUNTDOWN, Event.PERIOD_START)
    assert all(tick.phase is Phase.COUNTDOWN for tick in countdown)
    assert all(tick.event is None for tick in countdown[1:])
    assert all(positions(tick) == positions(ticks[0]) for tick in countdown)
    assert all(tick.elapsed == 0 for tick in countdown)
    assert first_play.phase is Phase.PLAYING
    assert positions(first_play) != positions(ticks[0])  # ya corren los behaviors


# --- fin por tiempo -----------------------------------------------------------


def test_ends_after_3_minutes_without_pauses_and_a_draw_is_allowed():
    ticks = play(club(0), club(10))

    assert len(ticks) == COUNTDOWN_TICKS + 3 * 60 * C.TICKS_PER_SECOND
    assert {tick.phase for tick in ticks[:-1]} == {Phase.COUNTDOWN, Phase.PLAYING}
    assert all(tick.period == 1 for tick in ticks)
    last = ticks[-1]
    assert (last.phase, last.event) == (Phase.FINISHED, Event.MATCH_END)
    assert (last.score_1, last.score_2) == (0, 0)  # empate, sin penales
    assert last.elapsed == pytest.approx(180)


# --- goles --------------------------------------------------------------------


def test_goal_counts_and_next_tick_everyone_is_back_at_the_start():
    club_2 = club(10, {role: OUT_OF_THE_WAY for role in C.STARTER_ROLES})
    session = build_test_session(club(0, {MemberRole.forward: FORWARD_CODE}), club_2, seed=1)
    start = positions(session.advance())
    ticks = []
    while not ticks or ticks[-1].event is not Event.GOAL:
        ticks.append(session.advance())
    goal, after = ticks[-1], session.advance()

    assert (goal.scoring_team, goal.score_1, goal.score_2) == (Team.HOME, 1, 0)
    assert goal.state.ball.position.x > C.FIELD_LENGTH  # el tick del gol la muestra adentro
    assert positions(after) == start
    assert (after.state.ball.position, after.state.ball.owner) == (FIELD_CENTER, None)
    assert (after.phase, after.event) == (Phase.PLAYING, None)
    assert after.elapsed > goal.elapsed  # el reloj sigue corriendo


# --- la alineación ------------------------------------------------------------


def test_each_player_plays_in_its_club_and_role_with_its_behavior():
    club_2 = club(10, {MemberRole.midfield: "go_to(0, 0)"})
    session = build_test_session(club(0), club_2, seed=1)
    ticks = [session.advance() for _ in range(COUNTDOWN_TICKS + C.TICKS_PER_SECOND)]
    before, after = positions(ticks[0]), positions(ticks[-1])

    ids = {player.key: player.player_id for player in ticks[0].state.players}
    assert ids == {
        (Team.HOME, 1): 1,
        (Team.HOME, 2): 2,
        (Team.HOME, 3): 3,
        (Team.AWAY, 1): 11,
        (Team.AWAY, 2): 12,
        (Team.AWAY, 3): 13,
    }
    moved = [key for key in before if after[key] != before[key]]
    assert moved == [(Team.AWAY, 2)]
    # (0, 0) es relativo a club2: en coordenadas absolutas, hacia (100, 60).
    assert after[(Team.AWAY, 2)].x > before[(Team.AWAY, 2)].x
