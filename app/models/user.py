from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    # Hash de la contraseña, nunca el texto plano. El límite de 72 del YAML
    # aplica a lo que envía el cliente, no al hash, por eso el largo es mayor.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    club_name: Mapped[str] = mapped_column(String(20), nullable=False)
    # Text y no String(n): el formato del avatar (URL, preset, base64) no está definido.
    avatar: Mapped[str] = mapped_column(Text, nullable=False)