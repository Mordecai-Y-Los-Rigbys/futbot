import enum


class BehaviorType(str, enum.Enum):
    """Tipo de un behavior (BehaviorType del contrato)."""

    player_behavior = "playerBehavior"
    coach_behavior = "coachBehavior"


class CodeRule(str, enum.Enum):
    """Regla de validez que incumple el código de un behavior (`rule` de CodeError)."""

    syntax_error = "syntaxError"
    import_not_allowed = "importNotAllowed"
    call_not_allowed = "callNotAllowed"
    function_definition_not_allowed = "functionDefinitionNotAllowed"
    class_not_allowed = "classNotAllowed"
    loop_not_allowed = "loopNotAllowed"
    comprehension_not_allowed = "comprehensionNotAllowed"
    global_not_allowed = "globalNotAllowed"
    primitive_assignment_not_allowed = "primitiveAssignmentNotAllowed"
    primitive_not_allowed_for_type = "primitiveNotAllowedForType"
    construct_not_allowed = "constructNotAllowed"
