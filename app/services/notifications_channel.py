from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from app.repositories.notification_abstract import NotificationData, NotificationsState
from app.services.friendly_service import to_match_club
from app.services.league_channel_handshake import ValidSessions, authorize_session
from app.services.league_channel_manager import LeagueChannelManager, LeagueChannelSpec, LoadState
from app.services.match_service import penalties_payload


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_notification(n: NotificationData) -> dict:
    item = {
        "id": n.id,
        "kind": "leagueFinished" if n.match is None else "matchFinished",
        "leagueId": n.league_id,
        "leagueMatchId": n.league_match_id,
        "seen": n.seen,
        "createdAt": _iso(n.created_at),
    }
    if n.match is None:
        item["leagueName"] = n.league_name
    else:
        item["club1"] = to_match_club(n.match.club1).model_dump(by_alias=True)
        item["club2"] = to_match_club(n.match.club2).model_dump(by_alias=True)
        item["result"] = {
            "score1": n.match.score_1,
            "score2": n.match.score_2,
            "penalties": penalties_payload(n.match.penalties),
        }
    return item


def build_notifications_payload(state: NotificationsState) -> dict:
    """Mensaje `notifications` del AsyncAPI."""
    return {
        "type": "notifications",
        "new": state.has_unseen,
        "notifications": [_to_notification(n) for n in state.notifications],
    }


NOTIFICATIONS_CHANNEL = LeagueChannelSpec(
    build_payload=build_notifications_payload,
    close_reasons={},  # no cierra por estado
)


@dataclass(frozen=True)
class NotificationsGrant:
    """Usuario y sesión de un handshake aceptado."""

    user_id: int
    session_id: str
    session_expires_at: datetime


class NotificationsHandshakeService:
    """Valida el handshake de /ws/notifications. El 429 lo aplica el manager."""

    def __init__(self, allowed_origins: Collection[str], sessions: ValidSessions) -> None:
        self.allowed_origins = set(allowed_origins)
        self.sessions = sessions

    def authorize(self, origin: str | None, session_id: str | None) -> NotificationsGrant:
        """Raises:
        ApiError 403 originNotAllowed: falta el header Origin o no está permitido.
        ApiError 401 sessionInvalid: sin cookie o con una sesión inválida o vencida.
        """
        session = authorize_session(self.allowed_origins, self.sessions, origin, session_id)
        return NotificationsGrant(
            user_id=session.user_id,
            session_id=session.id,
            session_expires_at=session.expires_at,
        )


class NotificationsManager(LeagueChannelManager):
    """Conexiones a /ws/notifications.

    Reutiliza la base de los canales de liga, pero registra por usuario: donde
    la base usa `league_id` como clave, acá va el user_id.
    """

    def __init__(self, load_state: LoadState) -> None:
        super().__init__(load_state, NOTIFICATIONS_CHANNEL)

    def notifications_changed(self, user_ids: Iterable[int]) -> None:
        """Se crearon o cambiaron notificaciones de estos usuarios. Llamar después del commit."""
        for user_id in set(user_ids):
            self.notify(user_id)
