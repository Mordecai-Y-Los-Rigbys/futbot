from app.domain.behavior import BehaviorType
from app.schemas.base import CamelModel


class BehaviorSummary(CamelModel):
    """Solo id, nombre y tipo. El código no se expone acá (ver GET /behaviors/{id})."""

    id: int
    name: str
    type: BehaviorType


class BehaviorPage(CamelModel):
    items: list[BehaviorSummary]
    page: int
    page_size: int
    total: int


class BehaviorDetail(CamelModel):
    id: int
    name: str
    type: BehaviorType
    code: str
    deletable: bool
