from fastapi import APIRouter, Depends, Query

from app.api.deps import get_behavior_service, get_current_user_id
from app.helpers.ids import parse_path_id as _parse_id
from app.api.pagination import parse_page
from app.schemas.behavior import BehaviorDetail, BehaviorPage, BehaviorSummary
from app.schemas.errors import Error, ListPageBadRequest
from app.services.behavior_service import PAGE_SIZE, BehaviorService

router = APIRouter(prefix="/behaviors", tags=["behaviors"])


# /me tiene que declararse ANTES que /{behavior_id}, si no este último lo tapa.
@router.get(
    "/me",
    response_model=BehaviorPage,
    responses={
        400: {"model": ListPageBadRequest},
        401: {"model": Error},
    },
)
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
        page_size=PAGE_SIZE,
        total=total,
    )


@router.get(
    "/{behavior_id}",
    response_model=BehaviorDetail,
    operation_id="getBehavior",
    responses={
        401: {"model": Error},
        403: {"model": Error},
        404: {"model": Error},
    },
)
def get_behavior(
    behavior_id: str,  # str y no int: un "abc" daría 422 antes de llegar acá
    user_id: int = Depends(get_current_user_id),  # 401 antes que el 404 del id
    service: BehaviorService = Depends(get_behavior_service),
):
    behavior = service.get_owned_behavior(user_id, _parse_id(behavior_id, "Comportamiento no encontrado."))
    return BehaviorDetail.model_validate(behavior)