from typing import Tuple
from app.errors import ApiError
from app.models.user import User
from app.repositories.user_abstract import AbstractUserRepository
from app.schemas.auth import RegisterUserRequest
from app.services.behavior_service import BehaviorService
from app.services.security_service import hash_password, verify_password
from app.services.session_service import SessionService


class AuthService:
    def __init__(
        self, 
        user_repo: AbstractUserRepository,
        session_service: SessionService,
        behavior_service: BehaviorService,
    ):
        self.user_repo = user_repo
        self.session_service = session_service
        self.behavior_service = behavior_service

    def register(self, request: RegisterUserRequest) -> Tuple[User, str]:
        """
        Registra un nuevo usuario, valida duplicados y crea su sesión inicial.
        Devuelve (User, session_id).
        """
        if self.user_repo.get_by_email(request.email) is not None:
            raise ApiError(
                status_code=409,
                code=None,
                message="El email ya está asociado a otro usuario.",
            )

        password_hash = hash_password(request.password)
        new_user = self.user_repo.create(
            username=request.username,
            email=request.email,
            password_hash=password_hash,
            club_name=request.club_name,
            avatar=request.avatar,
        )

        self.behavior_service.create_default_behaviors(new_user.id)

        user_session = self.session_service.create(user_id=new_user.id)
        return new_user, user_session.id

    def login(self, email: str, password: str) -> Tuple[User, str]:
        """
        Autentica credenciales y crea la sesión correspondiente.
        Devuelve (User, session_id).
        """
        if len(password) > 72:
            raise ApiError(
                status_code=401,
                code=None,
                message="Email o contraseña incorrectos.",
            )

        user = self.user_repo.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise ApiError(
                status_code=401,
                code=None,
                message="Email o contraseña incorrectos.",
            )

        user_session = self.session_service.create(user_id=user.id)
        return user, user_session.id