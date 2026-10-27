"""Aviso de cambios en los participantes de una liga.

El canal /ws/leagues/{id}/participants (AsyncAPI) todavía no existe. Este
módulo define el punto de enganche: los endpoints que cambian la lista
(inscribirse, abandonar) llaman a `publish(league_id)` DESPUÉS de confirmar el
cambio en la base. Cuando se implemente el canal, su publicador lee la lista
completa y el `leagueStatus` y la envía a los suscriptores; acá no cambia nada,
solo se reemplaza el publicador que devuelve `get_league_participants_publisher`.
"""

from typing import Protocol


class LeagueParticipantsPublisher(Protocol):
    async def publish(self, league_id: int) -> None:
        """Emite la lista completa y actualizada de participantes de la liga."""


class NoopLeagueParticipantsPublisher:
    """Publicador por defecto mientras no existe el canal: no emite nada."""

    async def publish(self, league_id: int) -> None:
        return None


_publisher: LeagueParticipantsPublisher = NoopLeagueParticipantsPublisher()


def get_league_participants_publisher() -> LeagueParticipantsPublisher:
    """Dependencia de FastAPI. Los tests la reemplazan con un fake."""
    return _publisher
