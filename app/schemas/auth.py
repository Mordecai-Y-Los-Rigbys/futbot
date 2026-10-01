from typing import Literal

from pydantic import BaseModel, Field, EmailStr, ConfigDict


class RegisterUserRequest(BaseModel):

    username: str = Field(min_length=1, max_length=20)
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)
    club_name: str = Field(alias="clubName", min_length=1, max_length=20)
    avatar: int = Field(ge=1, le=5)


class UserResponse(BaseModel):

    id: int
    username: str
    club_name: str = Field(serialization_alias="clubName")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class RegisterUserFieldError(BaseModel):

    field: Literal["username", "email", "password", "clubName", "avatar"]
    reason: Literal["required", "tooLong", "invalidEmail"]


class RegisterUserBadRequest(BaseModel):

    code: Literal["invalidFields"] = "invalidFields"
    message: str
    errors: list[RegisterUserFieldError]


class ErrorResponse(BaseModel):

    code: str | None
    message: str
    
class LogInRequest(BaseModel):
    
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)