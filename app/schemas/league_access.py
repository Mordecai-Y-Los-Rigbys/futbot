from typing import Literal

from pydantic import BaseModel


class UnlockLeagueForbidden(BaseModel):
    code: Literal["invalidLeaguePassword"]
    message: str


class LeagueAccessForbidden(BaseModel):
    code: Literal["leagueAccessRequired"]
    message: str
