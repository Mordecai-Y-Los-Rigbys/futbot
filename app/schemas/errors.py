from typing import Literal

from pydantic import BaseModel, Field

from app.domain.behavior import CodeRule
from app.schemas.base import CamelModel


class Error(BaseModel):
    code: str | None = None
    message: str


class LeagueDataConflict(BaseModel):
    code: Literal["leagueNotStarted", "leagueCancelled"]
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


class SubstitutionsConflict(BaseModel):
    # Se informa un solo motivo, el primero en este orden.
    code: Literal["matchNotStarted", "matchInPenalties", "noPausesLeft"]
    message: str


class SubstitutePlayerConflict(BaseModel):
    # Mismos códigos que el GET, pero noPausesLeft también sale durante la última pausa.
    # Se informa un solo motivo, el primero en este orden.
    code: Literal["matchNotStarted", "matchInPenalties", "noPausesLeft"]
    message: str


# --- PUT /matches/{id}/behavior ------------------------------------------------


class MatchBehaviorForbidden(BaseModel):
    code: Literal["notAPlayerInMatch", "playerNotStarter"]
    message: str


class MatchBehaviorConflict(BaseModel):
    code: Literal["matchNotInProgress", "playerOrBehaviorNotOwned", "behaviorTypeMismatch"]
    message: str


class TestBehaviorConflict(BaseModel):
    code: Literal["notPlayerBehavior", "playerOrBehaviorNotOwned", "behaviorTypeMismatch"]
    message: str


# --- POST /behaviors -----------------------------------------------------------


class CodeError(BaseModel):
    rule: CodeRule
    line: int
    column: int


class CreateBehaviorConflict(CamelModel):
    code: Literal["duplicateName", "codeTooLong", "invalidCode"]
    message: str
    code_error: CodeError | None


# --- PUT /behaviors/{id} ------------------------------------------------------


class UpdateBehaviorNotFound(BaseModel):
    code: Literal["notFound", "deletedConcurrently"]
    message: str
