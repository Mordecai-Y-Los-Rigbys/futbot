from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models.user import User
from app.repositories.user_abstract import AbstractUserRepository


class SqlAlchemyUserRepository(AbstractUserRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def create(
        self,
        username: str,
        email: str,
        password_hash: str,
        club_name: str,
        avatar: int,
    ) -> User:
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            club_name=club_name,
            avatar=avatar,
        )
        try:
            # begin_nested se usa como Savepoint: el INSERT llega a la db
            # y se chequea el email duplicado, pero no se commitea. 
            # El commit se hace en la creación de la sesión: 
            # usuario, behaviors y sesión se guardan juntos o no se guarda nada. 
            # Si el INSERT falla, solo se deshace el savepoint y la sesión sigue usable.
            with self.db.begin_nested():
                self.db.add(new_user)  
        except IntegrityError:
            raise ApiError(
                status_code=409,
                code=None,
                message="El email ya está asociado a otro usuario.",
            )
        self.db.refresh(new_user)
        return new_user
