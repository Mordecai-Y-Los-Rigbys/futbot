from abc import ABC, abstractmethod

from app.models.user import User


class AbstractUserRepository(ABC):
    """Contrato de acceso a usuarios. Las capas de servicio dependen de esta
    interfaz y no de la implementación con SQLAlchemy."""

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Devuelve el usuario con ese email, o None si no existe."""

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None:
        """Devuelve el usuario con ese id, o None si no existe."""

    @abstractmethod
    def create(
        self,
        username: str,
        email: str,
        password_hash: str,
        club_name: str,
        avatar: int,
    ) -> User:
        """Persiste un usuario nuevo. Lanza ApiError 409 si el email ya existe."""
