from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        CheckConstraint("power BETWEEN 20 AND 100", name="ck_players_power"),
        CheckConstraint("agility BETWEEN 20 AND 100", name="ck_players_agility"),
        CheckConstraint("control BETWEEN 20 AND 100", name="ck_players_control"),
        CheckConstraint("strength BETWEEN 20 AND 100", name="ck_players_strength"),
        CheckConstraint("speed BETWEEN 20 AND 100", name="ck_players_speed"),
        CheckConstraint(
            "power + agility + control + strength + speed = 300",
            name="ck_players_stats_sum",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    power: Mapped[int] = mapped_column(Integer, nullable=False)
    agility: Mapped[int] = mapped_column(Integer, nullable=False)
    control: Mapped[int] = mapped_column(Integer, nullable=False)
    strength: Mapped[int] = mapped_column(Integer, nullable=False)
    speed: Mapped[int] = mapped_column(Integer, nullable=False)
