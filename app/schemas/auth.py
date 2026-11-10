from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

MAX_EMAIL_LENGTH = 254


class RegisterUserRequest(BaseModel):

    username: str = Field(min_length=1, max_length=20)
    email: EmailStr = Field(json_schema_extra={"maxLength": MAX_EMAIL_LENGTH})
    password: str = Field(min_length=1, max_length=72)
    club_name: str = Field(alias="clubName", min_length=1, max_length=20)
    avatar: int = Field(strict=True, ge=1, le=5)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_length(cls, value: object) -> object:
        if isinstance(value, str) and len(value) > MAX_EMAIL_LENGTH:
            raise ValueError(f"El email supera el máximo de {MAX_EMAIL_LENGTH} caracteres.")
        return value


class User(BaseModel):

    id: int
    username: str
    club_name: str = Field(serialization_alias="clubName")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ErrorResponse(BaseModel):

    code: str | None
    message: str


class LogInRequest(BaseModel):

    email: EmailStr
    password: str = Field(min_length=1)

