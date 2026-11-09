"""Reglas de la prueba de un comportamiento.

La prueba no es un partido, pero se juega como uno: un 3 contra 3 con los
jugadores del usuario, en el club, el rol y con el behavior que eligió para
cada uno. Usa las reglas del amistoso (misma duración, se admiten empates) en
un solo período, sin pausas:

    countdown (3 s) | playing (3 min, el último tick es `finished`)

No hay DT, sustituciones ni cambios de comportamiento: nadie interviene. Como
en el partido, las reglas no esperan entre ticks: el ritmo lo pone la
transmisión.
"""

from app.repositories.team_abstract import StarterData
from app.services.match_setup_service import build_team
from app.simulation.constants import BEHAVIOR_TEST_COUNTDOWN_SECONDS, FRIENDLY_MATCH_DURATION
from app.simulation.match_rules import MatchSession, build_session


def build_test_session(
    club_1: list[StarterData], club_2: list[StarterData], seed: int
) -> MatchSession:
    """Arma los dos clubes de la prueba y la sesión que la simula.

    Raises:
        ValueError: algún club no tiene exactamente un titular por rol.
    """
    return build_session(
        build_team(club_1),
        build_team(club_2),
        FRIENDLY_MATCH_DURATION * 60,
        seed,
        countdown_seconds=BEHAVIOR_TEST_COUNTDOWN_SECONDS,
        periods=1,
        pause_seconds=0,
    )
