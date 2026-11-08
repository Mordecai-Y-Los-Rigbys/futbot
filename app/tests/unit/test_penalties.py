"""Tanda de penales: reglas del motor, sin base ni tiempo real.

Los comportamientos y el partido de prueba están en `penalty_helpers.py`.
"""

from app.simulation.geometry import Vec
from app.simulation.match_rules import Event, Phase
from app.simulation.state import BallState, Team
from app.tests.unit.penalty_helpers import DURATION, IDLE, OWN, SCORE, play


def shootout_ticks(ticks: list) -> list:
    return [t for t in ticks if t.phase is Phase.PENALTIES]


def test_tied_match_in_penalties_mode_goes_to_a_shootout():
    ticks = play(allow_draws=False)
    regular = ticks[: DURATION * 20]
    shootout = shootout_ticks(ticks)
    last = ticks[-1]

    assert all(t.phase is Phase.PLAYING for t in regular)
    assert ticks[len(regular)] is shootout[0]
    assert shootout[0].event is Event.PENALTIES_START
    assert len(shootout) == len(ticks) - len(regular) - 1
    assert last.phase is Phase.FINISHED and last.event is Event.MATCH_END
    assert last.shootout.winner is not None


def test_tied_match_in_normal_mode_ends_as_a_draw():
    ticks = play(allow_draws=True)

    assert len(ticks) == DURATION * 20
    assert ticks[-1].phase is Phase.FINISHED
    assert (ticks[-1].score_1, ticks[-1].score_2) == (0, 0)
    assert ticks[-1].shootout is None


def test_match_that_is_not_tied_has_no_shootout():
    # La pelota arranca entrando al arco de club2: gol de club1 en el primer tick.
    into_goal = BallState(position=Vec(99.0, 30.0), velocity=Vec(50.0, 0.0))
    ticks = play(allow_draws=False, ball=into_goal)

    assert (ticks[-1].score_1, ticks[-1].score_2) == (1, 0)
    assert ticks[-1].phase is Phase.FINISHED
    assert ticks[-1].shootout is None


def test_clubs_alternate_starting_with_club1_and_starters_kick_in_cycle():
    kicks = play(IDLE, IDLE)[-1].shootout.kicks  # nadie convierte: se patean los 10

    assert [(k.team, k.kicker_id, k.round) for k in kicks] == [
        (Team.HOME, 3, 1),
        (Team.AWAY, 13, 1),
        (Team.HOME, 2, 2),
        (Team.AWAY, 12, 2),
        (Team.HOME, 1, 3),
        (Team.AWAY, 11, 3),
        (Team.HOME, 3, 4),
        (Team.AWAY, 13, 4),
        (Team.HOME, 2, 5),
        (Team.AWAY, 12, 5),
    ]
    assert kicks[0].kicker_name == "J3"


def test_the_rival_defender_defends_and_only_both_are_on_the_field():
    for tick in shootout_ticks(play(SCORE, IDLE)):
        current = tick.shootout.current
        rival_defender = 11 if current.team is Team.HOME else 1
        assert current.defender_id == rival_defender
        assert current.defender_name == f"J{rival_defender}"
        assert {p.player_id for p in tick.state.players} == {current.kicker_id, rival_defender}


def test_each_kick_has_a_3_second_countdown_and_8_seconds_to_score():
    first_kick = shootout_ticks(play(IDLE, IDLE))[:220]
    countdown = first_kick[:60]
    playing = first_kick[60:]

    assert [t.shootout.countdown_seconds for t in countdown] == [3] * 20 + [2] * 20 + [1] * 20
    assert all(t.shootout.remaining_seconds == 8 for t in countdown)
    assert all(t.shootout.countdown_seconds is None for t in playing)
    assert playing[0].shootout.remaining_seconds == 8
    assert playing[-1].shootout.remaining_seconds == 0
    # Se agotaron los 8 s: el penal termina en el tick 160 de juego, errado.
    assert [t.event for t in playing].index(Event.PENALTY_KICK) == 159
    assert playing[-1].penalty_kick.scored is False


def test_a_ball_in_the_kickers_own_goal_ends_the_kick_without_scoring():
    ticks = shootout_ticks(play(OWN, IDLE))
    end = next(t for t in ticks if t.event is Event.PENALTY_KICK)

    assert end.penalty_kick.team is Team.HOME
    assert end.penalty_kick.scored is False
    assert ticks.index(end) < 60 + 159  # se cortó antes de los 8 s
    assert end.shootout.score_1 == 0
    assert end.shootout.score_2 == 0  # el gol en contra tampoco suma para el rival


def test_the_shootout_ends_when_a_club_can_no_longer_be_caught():
    last = play(SCORE, IDLE)[-1]

    # club1 convierte todos y club2 erra todos: después de 3 cada uno, club2
    # ya no llega (0 + 2 < 3).
    assert [k.scored for k in last.shootout.kicks] == [True, False] * 3
    assert (last.shootout.score_1, last.shootout.score_2) == (3, 0)
    assert last.shootout.winner is Team.HOME


def test_a_tied_shootout_is_drawn_with_the_match_seed():
    def winner(seed):
        return play(IDLE, IDLE, seed=seed)[-1].shootout.winner

    winners = {seed: winner(seed) for seed in range(1, 9)}

    assert all(winner(seed) is w for seed, w in winners.items())  # misma semilla, mismo ganador
    assert set(winners.values()) == {Team.HOME, Team.AWAY}  # es un sorteo, no siempre el mismo


def test_shootout_goals_do_not_count_in_the_score_and_the_clock_stops():
    ticks = play(SCORE, IDLE)
    elapsed_at_end = ticks[DURATION * 20 - 1].elapsed

    for tick in ticks[DURATION * 20 :]:
        assert (tick.score_1, tick.score_2) == (0, 0)
        assert tick.elapsed == elapsed_at_end


def test_every_kick_but_the_last_one_comes_with_a_penalty_kick_event():
    ticks = play(SCORE, IDLE)
    kicks = ticks[-1].shootout.kicks
    kick_events = [tick.penalty_kick for tick in ticks if tick.event is Event.PENALTY_KICK]

    # El último penal llega con matchEnd, que tiene prioridad.
    assert len(kick_events) == len(kicks) - 1
    assert kick_events == list(kicks[:-1])
    assert ticks[-1].event is Event.MATCH_END


# Convierte solo si el comportamiento ve el reloj del partido parado en el último período.
STOPPED_CLOCK = (
    "if i_have_ball() and current_period() == 2 and remaining_time() == 0:\n"
    "    kick_to(field_length, 23)\n"
)


def test_during_the_shootout_the_clock_is_stopped_in_the_last_period():
    last = play(STOPPED_CLOCK, IDLE, periods=2)[-1]

    assert [kick.scored for kick in last.shootout.kicks] == [True, False] * 3
