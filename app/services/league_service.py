from typing import Any

from app.errors import ApiError
from app.repositories.behavior_abstract import AbstractBehaviorRepository
from app.repositories.league_abstract import (
    AbstractLeagueRepository,
    CreateLeagueData,
    CreateLeagueMemberData,
    LeagueListItemData,
)
from app.domain.league import LeagueStatus
from app.errors import ApiError
from app.helpers.ids import parse_path_id
from app.services.league_participants_notifier import LeagueParticipantsNotifier
from app.repositories.behavior_abstract import AbstractBehaviorRepository
from app.repositories.player_abstract import AbstractPlayerRepository
from app.schemas.league import LeagueCreator, LeagueDetail, LeaguePage, LeagueSummary
from app.services.league_validation import parse_create_league
from app.services.team_ownership import ensure_owned_team

PAGE_SIZE = 50

LEAGUE_NOT_FOUND_MESSAGE = "La liga no existe."


def _to_summary(item: LeagueListItemData) -> LeagueSummary:
    return LeagueSummary(
        id=item.id,
        name=item.name,
        creator=LeagueCreator(
            id=item.creator.id,
            username=item.creator.username,
            name=item.creator.club_name,  # el spec lo expone como `name`
            avatar=item.creator.avatar,
        ),
        status=item.status,
        participants_count=item.participants_count,
        max_participants=item.max_participants,
        private=item.private,
        allow_draws=item.allow_draws,
        created_at=item.created_at,
    )


class LeagueService:
    """Casos de uso de las ligas: listar, crear y obtener una."""

    def __init__(
        self,
        repo: AbstractLeagueRepository,
        players: AbstractPlayerRepository,
        behaviors: AbstractBehaviorRepository,
        notifier: LeagueParticipantsNotifier | None = None,
    ) -> None:
        self.repo = repo
        self.players = players
        self.behaviors = behaviors
        self.notifier = notifier

    def list_leagues(self, name: str | None, page: int) -> LeaguePage:
        """Lista paginada de las ligas.

        Args:
            name: filtro opcional por nombre. None o "" no filtran.
            page: número de página, ya validado.

        Returns:
            La página pedida, con PAGE_SIZE ligas como máximo.
        """
        data = self.repo.list_page(
            name=name or None,  # "" se trata como ausente
            offset=(page - 1) * PAGE_SIZE,
            limit=PAGE_SIZE,
        )
        return LeaguePage(
            items=[_to_summary(i) for i in data.items],
            page=page,
            page_size=PAGE_SIZE,
            total=data.total,
        )

    def create_league(self, creator_id: int, body: Any) -> LeagueSummary:
        """Crea una liga e inscribe al creador con su equipo.

        Args:
            creator_id: usuario autenticado que crea la liga.
            body: JSON del request, todavía sin validar.

        Raises:
            ApiError 400: el body no cumple el contrato (ver parse_create_league).
            ApiError 409: playerOrBehaviorNotOwned.

        Returns:
            La liga creada.
        """
        data = parse_create_league(body)  # todos los 400, en orden

        # 409: solo si no falló ningún 400
        ensure_owned_team(self.players, self.behaviors, creator_id, data.members)

        created = self.repo.create(
            CreateLeagueData(
                name=data.name,
                creator_id=creator_id,
                min_participants=data.min_participants,
                max_participants=data.max_participants,
                match_duration=data.match_duration,
                private=data.private,
                password=data.password,  # None si es pública
                members=[
                    CreateLeagueMemberData(
                        player_id=m.player_id,
                        behavior_id=m.behavior_id,
                        role=m.role,
                    )
                    for m in data.members
                ],
            )
        )
        return _to_summary(created)
    
    def leave_league(self, user_id: int, raw_league_id: str) -> None:
        """Quita al usuario de una liga en preparación y libera su cupo.

        Raises:
            ApiError 404: id inválido o liga inexistente.
            ApiError 409: notInPreparation, notParticipating o isCreator
                (se evalúan en ese orden).
        """
        league_id = parse_path_id(raw_league_id, "La liga no existe.")  # 404

        info = self.repo.get_leave_info(league_id)
        if info is None:
            raise ApiError(404, None, "La liga no existe.")

        if info.status != LeagueStatus.preparation:
            raise ApiError(409, "notInPreparation", "La liga ya no está en preparación.")
        if not self.repo.is_participant(league_id, user_id):
            raise ApiError(409, "notParticipating", "No participás en esta liga.")
        if info.creator_id == user_id:
            raise ApiError(409, "isCreator", "El creador no puede abandonar su propia liga.")

        self.repo.remove_participant(league_id, user_id)

        # Solo ante un abandono exitoso; un intento fallido no emite nada
        if self.notifier is not None:
            self.notifier.participants_changed(league_id)

    def get_league(self, league_id: int, user_id: int) -> LeagueDetail:
        """Detalle de una liga.

        Args:
            league_id: id ya parseado (1..2147483647).
            user_id: usuario autenticado, para calcular `joined`.

        Raises:
            ApiError 404: la liga no existe.
        """
        data = self.repo.get_detail(league_id, user_id)
        if data is None:
            raise ApiError(404, None, LEAGUE_NOT_FOUND_MESSAGE)

        return LeagueDetail(
            **dict(_to_summary(data)),
            min_participants=data.min_participants,
            joined=data.joined,
        )
