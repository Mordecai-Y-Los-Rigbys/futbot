from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user_id, get_ranking_service
from app.api.pagination import parse_page
from app.schemas.errors import Error, ValidationBadRequest
from app.schemas.ranking import GlobalRankingPage
from app.services.ranking_service import RankingService

router = APIRouter(prefix="/ranking", tags=["Ranking"])


@router.get(
    "",
    response_model=GlobalRankingPage,
    operation_id="getGlobalRanking",
    summary="Obtener el ranking global",
    responses={
        400: {"model": ValidationBadRequest},
        401: {"model": Error},
    },
)
def get_global_ranking(
    name: str | None = Query(default=None),
    page: str = Query(default="1"),  # str: un "abc" daría 422 antes de llegar acá
    _user_id: int = Depends(get_current_user_id),  # 401 antes que cualquier 400
    service: RankingService = Depends(get_ranking_service),
) -> GlobalRankingPage:
    return service.get_global_ranking(page=parse_page(page), name=name or None)
