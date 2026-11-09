import pytest

from app.models.behavior import Behavior
from app.models.player import Player
from app.repositories.behavior_test_lineup_sqlalchemy import SqlAlchemyBehaviorTestLineupRepository

pytestmark = pytest.mark.integration


def add_behavior(db_session, user, code):
    record = Behavior(user_id=user.id, name=f"b-{code}", code=code)
    db_session.add(record)
    db_session.commit()
    return record


def add_player(db_session, user, name):
    record = Player(
        user_id=user.id, name=name, power=80, agility=60, control=60, strength=60, speed=40
    )
    db_session.add(record)
    db_session.commit()
    return record


def test_behavior_codes_only_brings_existing_behaviors_of_the_user(db_session, create_user):
    owner, other = create_user("owner"), create_user("other")
    mine = add_behavior(db_session, owner, "pass")
    theirs = add_behavior(db_session, other, "go_to(0, 0)")

    codes = SqlAlchemyBehaviorTestLineupRepository(db_session).behavior_codes(
        owner.id, {mine.id, theirs.id, 999999}
    )

    assert codes == {mine.id: "pass"}


def test_players_brings_the_stats_and_name(db_session, create_user):
    owner = create_user("owner")
    player = add_player(db_session, owner, "Pibe")

    players = SqlAlchemyBehaviorTestLineupRepository(db_session).players(owner.id, [player.id])

    loaded = players[player.id]
    assert (loaded.name, loaded.power, loaded.speed) == ("Pibe", 80, 40)
