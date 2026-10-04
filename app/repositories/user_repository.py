from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models.user import User

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, username: str, email: str, password_hash: str, club_name: str, avatar: int) -> User:
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            club_name=club_name,
            avatar=avatar,
        )
        self.db.add(new_user)
        try:
            self.db.commit()
        except IntegrityError:
            # Sin el rollback la sesión queda inutilizable
            self.db.rollback()
            raise ApiError(
                status_code=409,
                code=None,
                message="El email ya está asociado a otro usuario.",
            )
        self.db.refresh(new_user)
        return new_user

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)