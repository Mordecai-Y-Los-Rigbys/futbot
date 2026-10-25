from pydantic import BaseModel


class FirstSubstitutionData(BaseModel):
    user_id: int  # equipo: usuario del integrante que sale
    starter_name: str
    substitute_name: str