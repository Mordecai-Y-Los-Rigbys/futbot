import enum

class MemberRole(str, enum.Enum):
    forward = "forward"
    midfield = "midfield"
    defense = "defense"
    substitute = "substitute"