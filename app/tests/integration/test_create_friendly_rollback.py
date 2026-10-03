import pytest

from app.models.match import Match
from app.models.match_member import MatchMember
from app.models.player import Player
from app.repositories.friendly_abstract import CreateFriendlyData, CreateFriendlyMemberData
from app.repositories.friendly_sqlalchemy import SqlAlchemyFriendlyRepository

pytestmark = pytest.mark.integration

ROLES = ["forward", "midfield", "defense", "substitute", "substitute", "substitute"]


def test_failure_while_saving_the_team_leaves_no_match(db_session, make_user, make_behaviors):
    user = make_user(1)
    players = [
        Player(user_id=user.id, name=f"J{i}", power=60, agility=60,
               control=60, strength=60, speed=60)
        for i in range(6)
    ]
    db_session.add_all(players)
    db_session.commit()
    behaviors = make_behaviors(user.id, [f"b{i}" for i in range(6)])

    members = [
        CreateFriendlyMemberData(player_id=p.id, behavior_id=b.id, role=r)
        for p, r, b in zip(players, ROLES, behaviors)
    ]
    # El último miembro repite el player_id del primero: viola la unicidad
    # (match_id, user_id, player_id) y la base rechaza el commit.
    members[-1] = CreateFriendlyMemberData(
        player_id=players[0].id, behavior_id=behaviors[-1].id, role="substitute"
    )

    repo = SqlAlchemyFriendlyRepository(db_session)
    with pytest.raises(Exception):
        repo.create_with_team(
            CreateFriendlyData(name="Amistoso", creator_id=user.id, members=members)
        )

    assert db_session.query(Match).count() == 0
    assert db_session.query(MatchMember).count() == 0
