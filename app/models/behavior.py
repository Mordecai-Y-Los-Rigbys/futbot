from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.domain.behavior import BehaviorType


class Behavior(Base):
    __tablename__ = "behaviors"

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
