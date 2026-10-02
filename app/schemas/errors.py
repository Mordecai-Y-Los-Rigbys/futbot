from typing import Literal

from pydantic import BaseModel


class Error(BaseModel):
    code: str | None = None
    message: str


class ListPageBadRequest(BaseModel):
    code: Literal["pageNotAnInteger", "pageBelowMinimum", "pageTooLarge"]
    message: str


class CreateLeagueBadRequest(BaseModel):
    code: Literal[
        "invalidFieldType",
        "incompleteForm",
        "nameTooLong",
        "minParticipantsTooLow",
        "maxLessThanMin",
        "matchDurationOutOfRange",
        "passwordTooLong",
        "invalidTeam",
    ]
    message: str


class CreateLeagueConflict(BaseModel):
    code: Literal["playerOrBehaviorNotOwned"]
    message: str
    
class CreatePlayerBadRequest(BaseModel):
    code: Literal[
        "invalidFieldType",
        "incompleteForm",
        "nameTooLong",
        "statOutOfRange",
        "statSumMismatch",
    ]
    message: str