from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MatchWsToken(Base):
    """`tokenWs` emitido por POST /matches/{id}/connections.

    Atado a un único usuario y a un único partido. Es reutilizable hasta que
    expire (permite reconectar sin pedir otro).
    """

    __tablename__ = "match_ws_tokens"

    # Token opaco, mismo formato que el id de sesión (secrets.token_urlsafe(32)).
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
