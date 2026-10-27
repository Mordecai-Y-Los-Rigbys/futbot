import secrets
from typing import Any

from app.errors import ApiError
from app.helpers.ids import parse_path_id
from app.repositories.league_abstract import (
    AbstractLeagueRepository,
    CreateLeagueData,
    CreateLeagueMemberData,
    JoinLeagueData,
    JoinLeagueStateConflict,
    LeagueListItemData,
)
from app.repositories.behavior_abstract import AbstractBehaviorRepository
from app.repositories.player_abstract import AbstractPlayerRepository
from app.schemas.league import LeagueCreator, LeaguePage, LeagueSummary
from app.services.join_league_validation import parse_join_league
from app.services.league_validation import parse_create_league
from app.services.team_ownership import ensure_owned_team, ensure_owned_typed_team

PAGE_SIZE = 50
LEAGUE_NOT_FOUND = "Liga no encontrada."

_JOIN_CONFLICT_MESSAGES: dict[str, str] = {
    "notInPreparation": "La liga ya no admite inscripciones.",
    "leagueFull": "La liga ya alcanzó su cupo máximo de participantes.",
    "alreadyParticipating": "Ya participás en esta liga.",
}


def _to_summary(item: LeagueListItemData) -> LeagueSummary:
    return LeagueSummary(
        id=item.id,
        name=item.name,
        creator=LeagueCreator(
            id=item.creator.id,
            username=item.creator.username,
            name=item.creator.club_name,  # el spec lo expone como `name`
        ),
        status=item.status,
        participants_count=item.participants_count,
        max_participants=item.max_participants,
        private=item.private,
        created_at=item.created_at,
    )


def _password_matches(given: str, stored: str | None) -> bool:
    # compare_digest: tiempo constante, no filtra cuántos caracteres coinciden.
    if stored is None:
        return False
    return secrets.compare_digest(given.encode("utf-8"), stored.encode("utf-8"))


def _raise_join_conflict(conflict: JoinLeagueStateConflict | None) -> None:
    if conflict is not None:
        raise ApiError(409, conflict, _JOIN_CONFLICT_MESSAGES[conflict])


class LeagueService:
    """Casos de uso de las ligas: listar, crear e inscribirse."""

    def __init__(
        self,
        repo: AbstractLeagueRepository,
        players: AbstractPlayerRepository,
        behaviors: AbstractBehaviorRepository,
    ) -> None:
        self.repo = repo
        self.players = players
        self.behaviors = behaviors

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

    def join_league(self, user_id: int, session_id: str, raw_league_id: str, body: Any) -> int:
        """Inscribe al usuario en una liga con su equipo (POST /leagues/{id}/participants).

        Orden de evaluación del contrato: 401 (lo resuelve la dependencia de
        sesión) > 404 > 400 > 403 > 409. La obligatoriedad de `password`
        depende de la liga, por eso el 404 va antes de validar el body.

        Args:
            user_id: usuario autenticado que se inscribe.
            session_id: sesión actual; si la liga es privada, queda desbloqueada en ella.
            raw_league_id: id de la ruta, todavía sin validar.
            body: JSON del request, todavía sin validar.

        Raises:
            ApiError 404: el id no es válido o la liga no existe.
            ValidationApiError 400: invalidFields, con todos los campos que fallan.
            ApiError 403: invalidLeaguePassword (liga privada, contraseña vacía o incorrecta).
            ApiError 409: notInPreparation, leagueFull, alreadyParticipating,
                playerOrBehaviorNotOwned o behaviorTypeMismatch, en ese orden.

        Returns:
            El id de la liga, para emitir los participantes actualizados.
        """

        league_id = parse_path_id(raw_league_id, LEAGUE_NOT_FOUND)  # 404
        state = self.repo.get_join_state(league_id, user_id)
        if state is None:
            raise ApiError(404, None, LEAGUE_NOT_FOUND)

        data = parse_join_league(body, private=state.private)  # 400

        # 403: después de los 400 y antes de los 409 que revelan estado, cupo
        # y participación. Se valida aunque la sesión ya tenga la liga
        # desbloqueada (convención 11).
        if state.private and not _password_matches(data.password or "", state.password):
            raise ApiError(403, "invalidLeaguePassword", "La contraseña de la liga es incorrecta.")

        # 409, en el orden del enum JoinLeagueConflict
        _raise_join_conflict(state.conflict())
        ensure_owned_typed_team(
            self.players, self.behaviors, user_id, data.members, data.coach_behavior_id
        )

        # El repositorio vuelve a chequear estado y cupo con la liga bloqueada:
        # otra inscripción pudo llegar entre la lectura de arriba y esta escritura.
        _raise_join_conflict(
            self.repo.join(
                JoinLeagueData(
                    league_id=league_id,
                    user_id=user_id,
                    session_id=session_id,
                    members=[
                        CreateLeagueMemberData(
                            player_id=m.player_id, behavior_id=m.behavior_id, role=m.role
                        )
                        for m in data.members
                    ],
                    coach_behavior_id=data.coach_behavior_id,
                    unlock_session=state.private,
                )
            )
        )
        return league_id
