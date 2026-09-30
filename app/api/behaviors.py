# app/api/behaviors.py  (agregalo al router existente)
import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.database import get_db
from app.errors import ApiError
from app.schemas.behavior import BehaviorDetail
from app.services.behavior_service import BehaviorService
from app.api.deps import get_behavior_service, get_current_user_id

router = APIRouter(prefix="/behaviors", tags=["Behaviors"])

MAX_ID = 2147483647
_ID_RE = re.compile(r"[0-9]{1,10}")


def parse_path_id(raw: str) -> int:
    """Un id que no puede identificar ningún recurso es un recurso inexistente (404)."""
    if not _ID_RE.fullmatch(raw):
        raise ApiError(404, None, "Comportamiento no encontrado.")
    value = int(raw)
    if value < 1 or value > MAX_ID:
        raise ApiError(404, None, "Comportamiento no encontrado.")
    return value


# ... GET /behaviors/me va ACÁ ARRIBA, antes de "/{behavior_id}" ...


@router.get("/{behavior_id}", response_model=BehaviorDetail)
def get_behavior(
    behavior_id: str,
    user_id: int = Depends(get_current_user_id),
    service: BehaviorService = Depends(get_behavior_service),
):
    return service.get_owned_behavior(user_id, parse_path_id(behavior_id))

