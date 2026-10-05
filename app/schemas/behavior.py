from app.schemas.base import CamelModel


class BehaviorSummary(CamelModel):
    """Solo id y nombre. El código no se expone acá (ver GET /behaviors/{id})."""

    id: int
    name: str


class BehaviorPage(CamelModel):
    items: list[BehaviorSummary]
    page: int
    page_size: int
    total: int


class BehaviorDetail(CamelModel):
    id: int
    name: str
    code: str
