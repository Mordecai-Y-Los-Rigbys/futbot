from typing import Any
from app.repositories.player_abstract import AbstractPlayerRepository
from app.schemas.player import PlayerResponse, PlayerStats
from app.services.player_validation import parse_create_player

PAGE_SIZE = 50


class PlayerService:
    """Casos de uso de los jugadores de un usuario: crear y listar."""

    def __init__(self, repository: AbstractPlayerRepository) -> None:
        self.repository = repository

    def create_player(self, user_id: int, body: Any) -> PlayerResponse:
        """Crea un jugador para el usuario.

        Args:
            user_id: usuario autenticado, dueño del jugador nuevo.
            body: JSON del request, todavía sin validar.

        Raises:
            ApiError 400: el body no cumple el contrato (ver parse_create_player).

        Returns:
            El jugador creado, con sus stats.
        """

        data = parse_create_player(body)

        player_data = self.repository.create(user_id=user_id, data=data)

        stats = PlayerStats(
            power=player_data.power,
            agility=player_data.agility,
            control=player_data.control,
            strength=player_data.strength,
            speed=player_data.speed,
        )

        return PlayerResponse(
            id=player_data.id, name=player_data.name, stats=stats, deletable=player_data.deletable
        )

    def get_user_players(
        self, user_id: int, name: str | None, page: int
    ) -> tuple[list[PlayerResponse], int]:
        """Lista paginada de los jugadores del usuario, ordenados por id.

        Args:
            user_id: usuario autenticado.
            name: filtro opcional por nombre. None no filtra.
            page: número de página, ya validado.

        Returns:
            Los jugadores de esa página (PAGE_SIZE como máximo) y la cantidad total
            de jugadores que cumplen el filtro, que el endpoint devuelve como `total`.
        """

        offset = (page - 1) * PAGE_SIZE

        players_data, total = self.repository.list_by_user(user_id, name, offset, PAGE_SIZE)

        items = []
        for p in players_data:
            stats = PlayerStats(
                power=p.power,
                agility=p.agility,
                control=p.control,
                strength=p.strength,
                speed=p.speed,
            )
            items.append(PlayerResponse(id=p.id, name=p.name, stats=stats, deletable=p.deletable))

        return items, total
