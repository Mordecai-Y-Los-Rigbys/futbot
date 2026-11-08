from typing import Literal

from pydantic import BaseModel, Field


class Error(BaseModel):
    code: str | None = None
    message: str


class CreateLeagueConflict(BaseModel):
    code: Literal["playerOrBehaviorNotOwned"]
    message: str


class LeaveLeagueConflict(BaseModel):
    code: Literal["notInPreparation", "notParticipating", "isCreator"]
    message: str


class StartLeagueConflict(BaseModel):
    code: Literal["notInPreparation", "notEnoughParticipants"]
    message: str


class CreateFriendlyMatchConflict(BaseModel):
    code: Literal["alreadyPlaying", "playerOrBehaviorNotOwned"]
    message: str


class JoinMatchForbidden(BaseModel):
    code: Literal["invalidLeaguePassword"]
    message: str


class MatchAccessForbidden(BaseModel):
    code: Literal["notAPlayerInMatch", "leagueAccessRequired"]
    message: str


class JoinMatchConflict(BaseModel):
    code: Literal["matchFinished", "matchCancelled", "matchNotCreatedYet"]
    message: str


class JoinFriendlyMatchConflict(BaseModel):
    code: Literal["notJoinable", "isOwnMatch", "alreadyPlaying", "playerOrBehaviorNotOwned"]
    message: str


# --- 400 de validación con el formato del contrato (convención 6) -------------

FieldReason = Literal[
    "required",
    "invalidType",
    "tooLong",
    "outOfRange",
    "invalidEmail",
    "invalidValue",
    "invalidSum",
    "lessThanMin",
    "invalidTeam",
    "notStarter",
    "notSubstitute",
]


class FieldError(BaseModel):
    field: str
    reason: FieldReason


class ValidationBadRequest(BaseModel):
    code: Literal["invalidFields"]
    message: str
    errors: list[FieldError] = Field(min_length=1)


# --- POST /leagues/{id}/participants ------------------------------------------


class JoinLeagueForbidden(BaseModel):
    code: Literal["invalidLeaguePassword"]
    message: str


class JoinLeagueConflict(BaseModel):
    code: Literal[
        "notInPreparation",
        "leagueFull",
        "alreadyParticipating",
        "playerOrBehaviorNotOwned",
        "behaviorTypeMismatch",
    ]
    message: str


class NextSubstitutionsConflict(BaseModel):
    code: Literal["matchNotStarted"]
    message: str


# --- PUT /matches/{id}/behavior ------------------------------------------------


class MatchBehaviorForbidden(BaseModel):
    code: Literal["notAPlayerInMatch", "playerNotStarter"]
    message: str


class MatchBehaviorConflict(BaseModel):
    code: Literal["matchNotInProgress", "playerOrBehaviorNotOwned", "behaviorTypeMismatch"]
    message: str
