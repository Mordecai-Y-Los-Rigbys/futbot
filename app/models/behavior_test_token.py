from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BehaviorTestToken(Base):
    """`tokenWs` emitido por POST /behaviors/{id}/test-connections.

    Atado a un único usuario y a un único behavior. Reutilizable hasta que expire.
    """

    __tablename__ = "behavior_test_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    behavior_id: Mapped[int] = mapped_column(
        ForeignKey("behaviors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)