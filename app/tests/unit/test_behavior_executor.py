import logging

import pytest

from app.simulation.actions import GoTo, KickTo, MoveInDirection, PlayerActions
from app.simulation.behaviors.executor import MissingBehaviorError, run_behaviors
from app.simulation.behaviors.primitives import MatchClock
from app.simulation.behaviors.sandbox import compile_behavior
from app.simulation.constants import FIELD_LENGTH, FIELD_WIDTH
from app.simulation.physics import step
from app.tests.unit.simulation_helpers import AWAY, HOME, player, state

CLOCK = MatchClock(elapsed=0.0, remaining=180.0)
H, A = (HOME, 1), (AWAY, 1)


def match():
    return state(player(HOME, 1, x=20.0), player(AWAY, 1, x=80.0), ball=(50.0, 30.0))


def actions_of(sources, s=None, **kwargs):
    s = s or match()
    behaviors = {p.key: compile_behavior(sources.get(p.key, "")) for p in s.players}
    return run_behaviors(s, behaviors, CLOCK, **kwargs)


def test_returns_the_requested_actions_in_absolute_coordinates():
    actions = actions_of({H: "go_to(10, 5)", A: "go_to(10, 5)"})
    assert actions[H] == PlayerActions(move=GoTo(10.0, 5.0))
    assert actions[A] == PlayerActions(move=GoTo(FIELD_LENGTH - 10.0, FIELD_WIDTH - 5.0))


def test_the_same_code_works_for_both_teams():
    actions = actions_of({H: "move_in_direction(1, 0)", A: "move_in_direction(1, 0)"})
    assert actions[H].move == MoveInDirection(1.0, 0.0)
    assert actions[A].move == MoveInDirection(-1.0, -0.0)


def test_with_two_go_to_the_second_one_wins():
    actions = actions_of({H: "go_to(1, 1)\ngo_to(2, 2)"})
    assert actions[H].move == GoTo(2.0, 2.0)


def test_an_empty_behavior_asks_for_nothing():
    actions = actions_of({H: "go_to(1, 1)"})
    assert actions[A] == PlayerActions()


def test_a_player_without_behavior_is_an_error():
    behaviors = {H: compile_behavior("go_to(1, 1)")}
    with pytest.raises(MissingBehaviorError):
        run_behaviors(match(), behaviors, CLOCK)


def test_a_failing_behavior_discards_everything_it_asked_for(caplog):
    with caplog.at_level(logging.WARNING):
        actions = actions_of({H: "kick_to(100, 30)\ngo_to(1, 1)\nx = 1 / 0"})
    assert actions[H] == PlayerActions()  # sigue con su último movimiento y no patea
    assert "Falló el comportamiento" in caplog.text


def test_an_invalid_primitive_call_is_a_failure():
    actions = actions_of({H: "go_to(1, 1)\nteammate_position(7)"})
    assert actions[H] == PlayerActions()


def test_a_timeout_discards_the_actions():
    def slow_timer(counter=[0]):
        counter[0] += 1
        return counter[0]  # cada consulta "tarda" 1 segundo

    actions = actions_of({H: "go_to(1, 1)\ngo_to(2, 2)"}, team_budget=0.5, timer=slow_timer)
    assert actions[H] == PlayerActions()


def counting_timer():
    """Reloj falso: cada consulta "tarda" 1 segundo. Así el tiempo que gasta
    un behavior depende de cuántas veces se consulta el reloj, no de la máquina."""
    now = [0]

    def timer():
        now[0] += 1
        return now[0]

    return timer


def test_a_team_shares_its_time_budget_and_does_not_touch_the_other_team(caplog):
    # Un go_to consulta el reloj unas 30 veces.
    # 200 asignaciones lo consultan más de 200: se pasan del presupuesto.
    s = state(
        player(HOME, 1, x=20.0),
        player(HOME, 2, x=30.0),
        player(AWAY, 1, x=80.0),
        ball=(50.0, 30.0),
    )
    sources = {
        (HOME, 1): "x = 1\n" * 200,
        (HOME, 2): "go_to(1, 1)",
        (AWAY, 1): "go_to(2, 2)",
    }

    with caplog.at_level(logging.WARNING):
        actions = actions_of(sources, s=s, team_budget=60, timer=counting_timer())

    # El primero del local se pasó del presupuesto: se descartan sus acciones.
    assert actions[(HOME, 1)] == PlayerActions()
    # Su compañero ni se ejecuta, porque el equipo ya no tiene tiempo.
    assert actions[(HOME, 2)] == PlayerActions()
    assert "Sin tiempo para el comportamiento de" in caplog.text
    # El visitante tiene su propio presupuesto y se ejecuta normal.
    # go_to(2, 2) en coordenadas del visitante es (98, 58) en absolutas.
    assert actions[(AWAY, 1)] == PlayerActions(move=GoTo(98.0, 58.0))


def test_a_failure_does_not_affect_the_other_players():
    actions = actions_of({H: "x = 1 / 0", A: "kick_to(0, 30)"})
    assert actions[H] == PlayerActions()
    assert actions[A] == PlayerActions(kick=KickTo(FIELD_LENGTH, FIELD_WIDTH - 30.0, force=100))


def test_variables_do_not_survive_between_ticks():
    actions_of({H: "go_to(1, 1)\nremembered = 1"})
    assert actions_of({H: "go_to(remembered, 1)"})[H] == PlayerActions()


@pytest.mark.parametrize("name", ["state", "behaviors", "programs", "key", "recorder"])
def test_the_code_cannot_see_the_engine_internals(name):
    actions = actions_of({H: f"x = {name}\ngo_to(1, 1)"})
    assert actions[H] == PlayerActions()


def test_actions_feed_the_physics():
    s = match()
    actions = actions_of({H: "ball = ball_position()\ngo_to(ball[0], ball[1])"}, s)
    after = step(s, actions).state
    assert after.player(H).position.x > s.player(H).position.x
