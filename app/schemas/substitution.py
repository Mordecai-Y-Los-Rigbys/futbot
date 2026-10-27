from app.schemas.base import CamelModel


class SubstitutionResponse(CamelModel):
    starter_name: str
    substitute_name: str


class NextSubstitutions(CamelModel):
    club1: SubstitutionResponse | None
    club2: SubstitutionResponse | None