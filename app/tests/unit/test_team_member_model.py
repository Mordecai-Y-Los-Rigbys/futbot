"""Metadata de TeamMember (sin base de datos). El comportamiento real de los
constraints se prueba en integration/test_team_member_constraints.py y
integration/test_team_integration.py."""
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app import models  # noqa: F401
from app.models.team_member import TeamMember

TABLE = TeamMember.__table__


def test_table_name_and_required_columns():
    assert TeamMember.__tablename__ == "team_members"
    for name in ("user_id", "player_id", "behavior_id", "role"):
        assert TABLE.c[name].nullable is False


def test_league_and_match_are_both_nullable_columns():
    assert TABLE.c.league_id.nullable is True
    assert TABLE.c.match_id.nullable is True


def test_cascades_with_the_match():
    fk = next(iter(TABLE.c.match_id.foreign_keys))
    assert fk.column.table.name == "matches"
    assert fk.ondelete == "CASCADE"


def test_league_team_is_tied_to_the_participant_and_cascades():
    composite = [
        c for c in TABLE.constraints
        if isinstance(c, ForeignKeyConstraint) and len(c.columns) == 2
    ]
    assert len(composite) == 1
    fk = composite[0]
    assert [c.name for c in fk.columns] == ["league_id", "user_id"]
    assert fk.elements[0].column.table.name == "league_participants"
    assert fk.ondelete == "CASCADE"


def test_exactly_one_owner_check_exists():
    names = {c.name for c in TABLE.constraints if isinstance(c, CheckConstraint)}
    assert "ck_team_members_exactly_one_owner" in names


def test_a_player_is_unique_per_owner_and_user():
    uniques = {
        tuple(c.name for c in con.columns)
        for con in TABLE.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert ("league_id", "user_id", "player_id") in uniques
    assert ("match_id", "user_id", "player_id") in uniques


def test_role_enum():
    t = TABLE.c.role.type
    assert t.name == "member_role"
    assert list(t.enums) == ["forward", "midfield", "defense", "substitute"]


def test_there_is_no_separate_match_members_table():
    from app.database import Base
    assert "match_members" not in Base.metadata.tables
    assert "league_participant_members" not in Base.metadata.tables


def test_mappers_configure():
    configure_mappers()