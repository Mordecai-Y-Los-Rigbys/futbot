import re
from typing import Literal

from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator

EMAIL_RE = re.compile(r"[^@\s]{1,64}@([^@\s.]{1,63}\.)+[^@\s.]{1,63}")

class RegisterUserRequest(BaseModel):

    username: str = Field(min_length=1, max_length=20)
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=72)
    club_name: str = Field(alias="clubName", min_length=1, max_length=20)
    avatar: int = Field(strict=True, ge=1, le=5)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        # Solo corre si el email ya pasó el tipo y el largo (min/max_length),
        # así que la precedencia required > invalidType > tooLong > invalidEmail
        # se cumple sola.
        if not EMAIL_RE.fullmatch(v):
            raise ValueError("invalid email")
        return v


class User(BaseModel):

    id: int
    username: str
    club_name: str = Field(serialization_alias="clubName")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class RegisterUserFieldError(BaseModel):

    field: Literal["username", "email", "password", "clubName", "avatar"]
    reason: Literal["required", "tooLong", "invalidEmail", "invalidType", "outOfRange"]


class RegisterUserBadRequest(BaseModel):

    code: Literal["invalidFields"] = "invalidFields"
    message: str
    errors: list[RegisterUserFieldError]


class ErrorResponse(BaseModel):

    code: str | None
    message: str


class LogInRequest(BaseModel):

    email: EmailStr
    password: str = Field(min_length=1)


class LogInBadRequest(BaseModel):

    code: Literal["invalidFieldType", "incompleteForm", "invalidEmail"]
    message: str
