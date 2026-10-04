from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models.user import User

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, username, email, password_hash, club_name, avatar) -> User:
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            club_name=club_name,
            avatar=avatar,
        )
        try:
            # SAVEPOINT: si el INSERT falla, solo se deshace este insert y no lo
            # que la transacción ya tenía pendiente. El commit lo hace quien cierra
            # el registro (SessionRepository.create).
            with self.db.begin_nested():
                self.db.add(new_user)  # el flush ocurre al salir del bloque
        except IntegrityError:
            raise ApiError(
                status_code=409,
                code=None,
                message="El email ya está asociado a otro usuario.",
            )
        self.db.refresh(new_user)
        return new_user