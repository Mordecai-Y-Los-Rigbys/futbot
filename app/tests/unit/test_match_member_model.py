from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import UniqueConstraint

from app import models  # noqa: F401
from app.models.match import Match
from app.models.match_member import MatchMember

TABLE = Match.__table__
MEMBER = MatchMember.__table__


def test_match_has_nullable_name_of_at_most_20_chars():
    assert TABLE.c.name.type.length == 20
    assert TABLE.c.name.nullable is True


def test_match_has_created_at_with_server_default():
    assert TABLE.c.created_at.nullable is False
    assert TABLE.c.created_at.server_default is not None


def test_friendly_can_be_built_with_a_name():
    assert Match(user_1_id=1, name="Partido amistoso 1").name == "Partido amistoso 1"


def test_match_member_columns():
    assert MatchMember.__tablename__ == "match_members"
    required = ("match_id", "user_id", "player_id", "behavior_id", "role")
    assert set(required) <= set(MEMBER.c.keys())
    assert all(not MEMBER.c[c].nullable for c in required)


def test_match_member_cascades_with_match():
    fk = next(iter(MEMBER.c.match_id.foreign_keys))
    assert fk.column.table.name == "matches"
    assert fk.ondelete == "CASCADE"


def test_match_member_reuses_member_role_enum():
    t = MEMBER.c.role.type
    assert t.name == "member_role"
    assert list(t.enums) == ["forward", "midfield", "defense", "substitute"]


def test_match_member_player_unique_per_match_and_user():
    uniques = [
        tuple(c.name for c in con.columns)
        for con in MEMBER.constraints
        if isinstance(con, UniqueConstraint)
    ]
    assert ("match_id", "user_id", "player_id") in uniques


def test_mappers_configure():
    configure_mappers()
