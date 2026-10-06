import enum


class MatchStatus(str, enum.Enum):
    """Mismos valores que `MatchStatus` del OpenAPI."""

    scheduled = "scheduled"  # todavía no se jugó
    started = "started"  # se está jugando ahora
    finished = "finished"  # ya tiene resultado
    cancelled = "cancelled"  # amistoso cuya espera venció sin rival
