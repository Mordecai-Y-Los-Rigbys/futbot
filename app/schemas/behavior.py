from pydantic import BaseModel, ConfigDict
from app.schemas.base import CamelModel


class BehaviorSummary(CamelModel):
    """Solo id y nombre. El código no se expone acá (ver GET /behaviors/{id})."""

    id: int
    name: str


class BehaviorPage(CamelModel):
    items: list[BehaviorSummary]
    page: int
<<<<<<< HEAD
    pageSize: int
    total: int


class BehaviorDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # pydantic v1: orm_mode = True

    id: int
    name: str
    code: str
=======
    page_size: int
    total: int
>>>>>>> aaff84b04eb8edecc4312480874a064b22e72e26
