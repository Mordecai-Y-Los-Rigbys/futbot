from sqlalchemy.orm import Session
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
        self.db.commit()
        self.db.refresh(new_user)
        return new_user