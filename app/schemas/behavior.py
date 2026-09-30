from pydantic import BaseModel, ConfigDict


class BehaviorSummary(BaseModel):
    """Solo id y nombre. El código no se expone acá (ver GET /behaviors/{id})."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class BehaviorPage(BaseModel):
    items: list[BehaviorSummary]
    page: int
    pageSize: int
    total: int
    