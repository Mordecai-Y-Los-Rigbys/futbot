from typing import Any

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import (
    get_behavior_service,
    get_behavior_test_connection_service,
    get_current_user_id,
    get_json_body,
)
from app.api.pagination import parse_page
from app.helpers.ids import parse_path_id as _parse_id
from app.schemas.behavior import (
    BehaviorDetail,
    BehaviorPage,
    BehaviorSummary,
    BehaviorTestConnectionResponse,
    behavior_test_request_schema,
)
from app.schemas.errors import (
    CreateBehaviorConflict,
    DeleteBehaviorConflict,
    Error,
    TestBehaviorConflict,
    UpdateBehaviorNotFound,
    ValidationBadRequest,
)
from app.services.behavior_service import BEHAVIOR_NOT_FOUND_MESSAGE, PAGE_SIZE, BehaviorService
from app.services.behavior_test_connection_service import BehaviorTestConnectionService

router = APIRouter(prefix="/behaviors", tags=["behaviors"])


@router.post(
    "",
    response_model=BehaviorDetail,
    status_code=201,
    operation_id="createBehavior",
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
        409: {"model": CreateBehaviorConflict},
    },
)
def create_behavior(
    user_id: int = Depends(get_current_user_id),  # se resuelve antes: 401 gana sobre 400
    body: Any = Depends(get_json_body),
    service: BehaviorService = Depends(get_behavior_service),
) -> BehaviorDetail:
    return service.create_behavior(user_id, body)


# /me tiene que declararse ANTES que /{behavior_id}, si no este último lo tapa.
@router.get(
    "/me",
    response_model=BehaviorPage,
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
    },
)
def list_behaviors(
    name: str | None = Query(default=None),
    page: str = Query(default="1"),
    user_id: int = Depends(get_current_user_id),  # se resuelve antes: 401 gana sobre 400
    service: BehaviorService = Depends(get_behavior_service),
) -> BehaviorPage:
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
) -> BehaviorDetail:
    return service.get_behavior(user_id, _parse_id(behavior_id, BEHAVIOR_NOT_FOUND_MESSAGE))


@router.put(
    "/{behavior_id}",
    response_model=BehaviorDetail,
    operation_id="updateBehavior",
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
        403: {"model": Error},
        404: {"model": UpdateBehaviorNotFound},
        409: {"model": CreateBehaviorConflict},
    },
)
def update_behavior(
    behavior_id: str,
    user_id: int = Depends(get_current_user_id),
    body: Any = Depends(get_json_body),
    service: BehaviorService = Depends(get_behavior_service),
) -> BehaviorDetail:
    parsed_id = _parse_id(behavior_id, BEHAVIOR_NOT_FOUND_MESSAGE, "notFound")
    return service.update_behavior(user_id, parsed_id, body)


@router.delete(
    "/{behavior_id}",
    status_code=204,
    operation_id="deleteBehavior",
    responses={
        401: {"model": Error},
        403: {"model": Error},
        404: {"model": Error},
        409: {"model": DeleteBehaviorConflict},
    },
)
def delete_behavior(
    behavior_id: str,
    user_id: int = Depends(get_current_user_id),
    service: BehaviorService = Depends(get_behavior_service),
) -> Response:
    service.delete_behavior(user_id, _parse_id(behavior_id, BEHAVIOR_NOT_FOUND_MESSAGE))
    return Response(status_code=204)


@router.post(
    "/{id}/test-connections",
    response_model=BehaviorTestConnectionResponse,
    status_code=201,
    operation_id="testBehavior",
    summary="Pedir conexión para probar un comportamiento de jugador",
    # El body se lee a mano (convención 9), así que FastAPI no lo documenta solo.
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": behavior_test_request_schema()}},
        }
    },
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
        403: {"model": Error},
        404: {"model": Error},
        409: {"model": TestBehaviorConflict},
    },
)
def test_behavior(
    id: str,
    user_id: int = Depends(get_current_user_id),  # 401 antes que el 404 del id
    body: Any = Depends(get_json_body),
    service: BehaviorTestConnectionService = Depends(get_behavior_test_connection_service),
) -> BehaviorTestConnectionResponse:
    token = service.connect(user_id, _parse_id(id, BEHAVIOR_NOT_FOUND_MESSAGE), body)
    return BehaviorTestConnectionResponse(token_ws=token)
