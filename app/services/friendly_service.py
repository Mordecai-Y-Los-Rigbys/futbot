from typing import Any

from app.errors import ApiError
from app.helpers.ids import parse_path_id
from app.repositories.friendly_abstract import (
    AbstractFriendlyRepository,
    CreateFriendlyData,
    CreateFriendlyMemberData,
    FriendlyMatchData,
    JoinFriendlyData,
)
from app.repositories.behavior_abstract import AbstractBehaviorRepository
from app.repositories.player_abstract import AbstractPlayerRepository
from app.schemas.friendly import MatchClub, MatchPage, MatchResponse
from app.services.friendly_validation import parse_create_friendly, parse_join_friendly
from app.services.team_ownership import ensure_owned_team

PAGE_SIZE = 50


def _to_response(m: FriendlyMatchData) -> MatchResponse:
    return MatchResponse(
        id=m.id,
        league_id=None,
        name=m.name,
        status=m.status,
        club1=MatchClub(id=m.club1.id, username=m.club1.username, name=m.club1.club_name),
        club2=(
            MatchClub(id=m.club2.id, username=m.club2.username, name=m.club2.club_name)
            if m.club2
            else None
        ),
        scheduled_at=None,
        created_at=m.created_at,
        result=None,
    )


def _not_found() -> ApiError:
    return ApiError(404, None, "Partido amistoso no encontrado.")


class FriendlyService:
    """Casos de uso de los amistosos: crear, listar los que esperan rival y unirse."""

    def __init__(
        self,
        repo: AbstractFriendlyRepository,
        players: AbstractPlayerRepository,
        behaviors: AbstractBehaviorRepository,
    ) -> None:
        self.repo = repo
        self.players = players
        self.behaviors = behaviors

    def create_friendly(self, creator_id: int, body: Any) -> MatchResponse:
        """Crea un amistoso con el equipo del creador y lo deja esperando rival.

        Args:
            creator_id: usuario autenticado que crea el amistoso.
            body: JSON del request, todavía sin validar.

        Raises:
            ApiError 400: el body no cumple el contrato (en el orden de la convención 6).
            ApiError 409: alreadyPlaying o playerOrBehaviorNotOwned.

        Returns:
            El amistoso creado, todavía sin rival.
        """

        data = parse_create_friendly(body)  # todos los 400, en orden

        # 409: solo si no falló ningún 400
        if self.repo.user_is_playing(creator_id):
            raise ApiError(409, "alreadyPlaying", "Ya estás jugando otro partido.")

        ensure_owned_team(self.players, self.behaviors, creator_id, data.members)

        created = self.repo.create_with_team(
            CreateFriendlyData(
                name=data.name,
                creator_id=creator_id,
                members=[
                    CreateFriendlyMemberData(
                        player_id=m.player_id, behavior_id=m.behavior_id, role=m.role
                    )
                    for m in data.members
                ],
            )
        )
        return _to_response(created)

    def list_waiting_friendlies(self, user_id: int, name: str | None, page: int) -> MatchPage:
        """Lista paginada de los amistosos que esperan rival, sin los del propio usuario.

        Args:
            user_id: usuario autenticado. Sus propios amistosos no se listan.
            name: filtro opcional por nombre. None o "" no filtran.
            page: número de página, ya validado.

        Returns:
            La página pedida, con PAGE_SIZE amistosos como máximo.
        """

        data = self.repo.list_waiting_page(
            exclude_user_id=user_id,
            name=name or None,  # "" se trata como ausente
            offset=(page - 1) * PAGE_SIZE,
            limit=PAGE_SIZE,
        )
        return MatchPage(
            items=[_to_response(i) for i in data.items],
            page=page,
            page_size=PAGE_SIZE,
            total=data.total,
        )

    def join_friendly(self, user_id: int, raw_match_id: str, body: Any) -> MatchResponse:
        """Une al usuario como rival de un amistoso que está esperando rival.

        Args:
            user_id: usuario autenticado que se une.
            raw_match_id: id de la ruta, todavía sin validar.
            body: JSON del request, todavía sin validar.

        Raises:
            ApiError 404: el id no es válido o el amistoso no existe.
            ApiError 400: el body no cumple el contrato (en el orden de la convención 6).
            ApiError 409: notJoinable, isOwnMatch, alreadyPlaying o playerOrBehaviorNotOwned.

        Returns:
            El partido con los dos clubes.
        """

        match_id = parse_path_id(raw_match_id, "Partido amistoso no encontrado.")  # 404
        state = self.repo.get_friendly_state(match_id)
        if state is None:
            raise _not_found()
        data = parse_join_friendly(body)  # 400, en orden

        # 409: en el orden del enum del contrato
        if state.status != "scheduled" or state.rival_id is not None:
            raise ApiError(409, "notJoinable", "El partido ya no admite un rival.")
        if state.creator_id == user_id:
            raise ApiError(409, "isOwnMatch", "No podés unirte a tu propio partido.")
        if self.repo.user_is_playing(user_id):
            raise ApiError(409, "alreadyPlaying", "Ya estás jugando otro partido.")

        ensure_owned_team(self.players, self.behaviors, user_id, data.members)

        joined = self.repo.join_friendly(
            JoinFriendlyData(
                match_id=match_id,
                user_id=user_id,
                members=[
                    CreateFriendlyMemberData(
                        player_id=m.player_id, behavior_id=m.behavior_id, role=m.role
                    )
                    for m in data.members
                ],
            )
        )
        if joined is None:  # la base decidió: otro llegó antes, o venció la espera
            raise ApiError(409, "notJoinable", "El partido ya no admite un rival.")
        return _to_response(joined)
