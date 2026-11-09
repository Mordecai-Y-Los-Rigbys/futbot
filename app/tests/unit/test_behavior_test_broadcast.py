"""Eventos del testTick que la prueba completa (todos quietos) no muestra."""

from app.domain.team_member import MemberRole
from app.repositories.team_abstract import StarterData
from app.services.behavior_test_broadcast import build_test_tick_payload
from app.services.behavior_test_rules import build_test_session
from app.simulation import constants as C
from app.simulation.behaviors.default_behaviors import FORWARD_CODE
from app.simulation.match_rules import Event

# Se va a una esquina de su propio arco: deja libre el camino hacia ese arco.
OUT_OF_THE_WAY = "go_to(0, 0)"


def club(first_id, code_by_role):
    return [
        StarterData(
            player_id=first_id + role.number,
            name=f"Jugador {first_id + role.number}",
            role=role,
            power=60,
            agility=60,
            control=60,
            strength=60,
            speed=60,
            behavior_code=code_by_role.get(role, "pass"),
        )
        for role in C.STARTER_ROLES
    ]


def test_a_goal_says_which_club_scored():
    club_1 = club(0, {role: OUT_OF_THE_WAY for role in C.STARTER_ROLES})
    club_2 = club(10, {MemberRole.forward: FORWARD_CODE})
    session = build_test_session(club_1, club_2, seed=1)
    result = session.advance()
    while not session.finished and result.event is not Event.GOAL:
        result = session.advance()
    assert result.event is Event.GOAL, "no hubo ningún gol en toda la prueba"

    payload = build_test_tick_payload(result)

    assert payload["event"] == {"type": "goal", "club": "club2"}
    assert (payload["score1"], payload["score2"]) == (0, 1)
