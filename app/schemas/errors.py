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


class CreateFriendlyMatchBadRequest(BaseModel):
    code: Literal["invalidFieldType", "incompleteForm", "nameTooLong", "invalidTeam"]
    message: str


class CreateFriendlyMatchConflict(BaseModel):
    code: Literal["alreadyPlaying", "playerOrBehaviorNotOwned"]
    message: str


class JoinFriendlyMatchBadRequest(BaseModel):
    code: Literal["invalidFieldType", "incompleteForm", "invalidTeam"]
    message: str


class JoinFriendlyMatchConflict(BaseModel):
    code: Literal[
        "notJoinable", "isOwnMatch", "alreadyPlaying", "playerOrBehaviorNotOwned"
    ]
    message: str
