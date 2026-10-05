import pytest
from sqlalchemy.exc import DataError, IntegrityError

from app.models.league_participant_member import MemberRole
from app.models.match import Match, MatchStatus
from app.models.match_member import MatchMember
from app.models.player import Player

pytestmark = pytest.mark.integration


@pytest.fixture()
def users(make_user):
    return make_user(1), make_user(2)


@pytest.fixture()
def team(db_session, users, make_behaviors):
    """(player_id, behavior_id) del usuario 1."""
    player = Player(
        user_id=users[0].id, name="Jugador",
        power=60, agility=60, control=60, strength=60, speed=60,  # suma 300
    )
    db_session.add(player)
    db_session.commit()
    behavior = make_behaviors(users[0].id, ["b"])[0]
    return player.id, behavior.id


def new_match(db_session, **fields):
    match = Match(**fields)
    db_session.add(match)
    db_session.commit()
    return match


def add_member(db_session, match_id, user_id, player_id, behavior_id,
               role=MemberRole.forward):
    db_session.add(MatchMember(
        match_id=match_id, user_id=user_id, player_id=player_id,
        behavior_id=behavior_id, role=role,
    ))
    db_session.commit()


def test_member_is_persisted_with_its_match(db_session, users, team):
    match = new_match(db_session, user_1_id=users[0].id, name="Amistoso")
    add_member(db_session, match.id, users[0].id, *team)
    member = db_session.query(MatchMember).one()
    assert member.match_id == match.id and member.role == MemberRole.forward


def test_deleting_the_match_deletes_its_team(db_session, users, team):
    match = new_match(db_session, user_1_id=users[0].id)
    add_member(db_session, match.id, users[0].id, *team)
    db_session.delete(match)
    db_session.commit()
    assert db_session.query(MatchMember).count() == 0


def test_same_player_twice_in_same_match_is_rejected(db_session, users, team):
    match = new_match(db_session, user_1_id=users[0].id)
    add_member(db_session, match.id, users[0].id, *team)
    db_session.add(MatchMember(
        match_id=match.id, user_id=users[0].id, player_id=team[0],
        behavior_id=team[1], role=MemberRole.defense,
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cancelled_friendly_without_rival_is_valid(db_session, users):
    new_match(db_session, user_1_id=users[0].id, status=MatchStatus.cancelled)
    assert db_session.query(Match).one().user_2_id is None


def test_name_longer_than_20_chars_is_rejected(db_session, users):
    db_session.add(Match(user_1_id=users[0].id, name="x" * 21))
    with pytest.raises((DataError, IntegrityError)):
        db_session.commit()
    db_session.rollback()


def test_created_at_is_filled_by_the_database(db_session, users):
    match = new_match(db_session, user_1_id=users[0].id)
    assert match.created_at is not None
