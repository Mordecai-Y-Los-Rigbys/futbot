from typing import Literal

from pydantic import BaseModel


class Error(BaseModel):
    code: str | None = None
    message: str


class ListPageBadRequest(BaseModel):
    code: Literal["pageNotAnInteger", "pageBelowMinimum", "pageTooLarge"]
    message: str