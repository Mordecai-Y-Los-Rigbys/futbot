from app.errors import ApiError
from app.models.user import User
from app.repositories.user_abstract import AbstractUserRepository


class UserService:
    def __init__(self, user_repo: AbstractUserRepository):
        self.user_repo = user_repo

    def get_by_id(self, user_id: int) -> User:
        """Devuelve el usuario de la sesión. Si la sesión es válida pero el
        usuario ya no existe, se trata como sesión inválida (401)."""
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise ApiError(401, None, "Sin sesión válida.")
        return user