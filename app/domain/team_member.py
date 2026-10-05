import enum

class MemberRole(str, enum.Enum):
    forward = "forward"
    midfield = "midfield"
    defense = "defense"
    substitute = "substitute"

    @property
    def number(self) -> int:
        if self is MemberRole.substitute:
            raise ValueError("un suplente no tiene número de cancha")
        return _ROLE_NUMBERS[self]

_ROLE_NUMBERS = {
    MemberRole.defense: 1,
    MemberRole.midfield: 2,
    MemberRole.forward: 3,
}
