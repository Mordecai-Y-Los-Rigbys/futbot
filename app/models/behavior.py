from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.domain.behavior import BehaviorType


class Behavior(Base):
    __tablename__ = "behaviors"
    __table_args__ = (
        # El nombre es único entre los behaviors no eliminados: al eliminar uno,
        # su nombre queda libre.
        Index(
            "uq_behaviors_user_id_name",
            "user_id",
            "name",
            unique=True,
            postgresql_where=text("NOT deleted"),
            sqlite_where=text("NOT deleted"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(Text, default="")
    # playerBehavior por defecto: los behaviors que ya se crean sin tipo
    # (behaviors por defecto del registro, fixtures de tests) son de jugador.
    type: Mapped[BehaviorType] = mapped_column(
        Enum(
            BehaviorType,
            name="behavior_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=BehaviorType.player_behavior,
        server_default=BehaviorType.player_behavior.value,
    )

    # Borrado lógico: la fila queda para los partidos ya jugados que lo usaron.
    deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
