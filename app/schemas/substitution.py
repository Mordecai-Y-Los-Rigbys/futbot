from app.schemas.base import CamelModel


class Substitution(CamelModel):
    starter_name: str
    substitute_name: str


class Substitutions(CamelModel):
    club1: Substitution | None
    club2: Substitution | None