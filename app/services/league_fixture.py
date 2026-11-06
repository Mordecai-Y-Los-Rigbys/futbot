import random
from datetime import datetime, timedelta
from itertools import combinations

from app.repositories.league_abstract import FixtureMatchData
from app.simulation.constants import COUNTDOWN_SECONDS, PAUSE_SECONDS, PERIODS

FIRST_MATCH_DELAY = timedelta(minutes=1)
# 3 pausas de 15s y 4 cuentas regresivas de 5s: 65s
BREAKS = timedelta(seconds=(PERIODS - 1) * PAUSE_SECONDS + PERIODS * COUNTDOWN_SECONDS)
# Máximo de la tanda: 10 penales (5 por club) de 3s de cuenta previa y 8s para patear
PENALTY_SHOOTOUT = timedelta(seconds=110)
MARGIN = timedelta(minutes=1)


def match_slot(match_duration: int, allow_draws: bool) -> timedelta:
    """Tiempo entre el inicio de un partido y el del siguiente.

    Args:
        match_duration: duración de cada partido, en minutos.
        allow_draws: False si la liga está en modo penales.
    """
    shootout = timedelta(0) if allow_draws else PENALTY_SHOOTOUT
    return timedelta(minutes=match_duration) + BREAKS + shootout + MARGIN


def build_fixture(
    participant_ids: list[int], started_at: datetime, slot: timedelta, rng: random.Random
) -> list[FixtureMatchData]:
    """Un partido por par de participantes, en orden al azar, uno cada `slot`.

    Ordena los ids antes de sortear: con la misma semilla, el fixture no
    depende del orden en que la base devuelve a los participantes.
    """
    pairs = list(combinations(sorted(participant_ids), 2))
    rng.shuffle(pairs)
    first = started_at + FIRST_MATCH_DELAY
    return [
        FixtureMatchData(user_1_id=a, user_2_id=b, scheduled_at=first + i * slot)
        for i, (a, b) in enumerate(pairs)
    ]
