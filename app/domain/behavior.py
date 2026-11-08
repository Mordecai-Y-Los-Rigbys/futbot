import enum


class BehaviorType(str, enum.Enum):
    """Tipo de un behavior (BehaviorType del contrato)."""

    player_behavior = "playerBehavior"
    coach_behavior = "coachBehavior"
