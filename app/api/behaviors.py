import re

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_behavior_service, get_current_user_id
from app.errors import ApiError
from app.schemas.behavior import BehaviorPage, BehaviorSummary
from app.services.behavior_service import PAGE_SIZE, BehaviorService
from app.api.pagination import parse_page


router = APIRouter(prefix="/behaviors", tags=["behaviors"])

MAX_PAGE = 2147483647
_INT_RE = re.compile(r"-?[0-9]+")  # solo dígitos ASCII


@router.get("/me", response_model=BehaviorPage)
def list_behaviors(
    name: str | None = Query(default=None),
    page: str = Query(default="1"),
    user_id: int = Depends(get_current_user_id),  # se resuelve antes: 401 gana sobre 400
    service: BehaviorService = Depends(get_behavior_service),
):
    page_number = parse_page(page)
    items, total = service.list_behaviors(user_id, name, page_number)
    return BehaviorPage(
        items=[BehaviorSummary.model_validate(i) for i in items],
        page=page_number,
        pageSize=PAGE_SIZE,
        total=total,
    )