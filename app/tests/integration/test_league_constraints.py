import pytest
from sqlalchemy.exc import IntegrityError

from app.models.league import League, LeagueStatus

pytestmark = pytest.mark.integration


def _league(creator, private, password):
    return League(
        name="Liga",
        creator_id=creator.id,
        status=LeagueStatus.preparation,
        min_participants=3,
        max_participants=8,
        match_duration=5,
        private=private,
        password=password,
    )


def test_private_league_without_password_is_rejected(db_session, create_user):
    owner = create_user("owner")
    db_session.add(_league(owner, private=True, password=None))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    "private, password",
    [(True, "secret"), (False, None), (False, "secret")],
)
def test_valid_combinations_are_accepted(db_session, create_user, private, password):
    owner = create_user("owner")
    db_session.add(_league(owner, private, password))
    db_session.commit()  # no debe lanzar