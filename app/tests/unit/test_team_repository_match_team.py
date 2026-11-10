from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.domain.behavior import BehaviorType
from app.domain.team_member import MemberRole
from app.repositories.team_sqlalchemy import SqlAlchemyTeamRepository


def literal_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def row(member_id, player_id, role, behavior_id=1, btype=BehaviorType.player_behavior):
    return SimpleNamespace(
        member_id=member_id,
        player_id=player_id,
        player_name=f"J{player_id}",
        role=role,
        behavior_id=behavior_id,
        behavior_name=f"B{behavior_id}",
        behavior_type=btype,
    )


@pytest.fixture()
def db():
    return MagicMock(spec=Session)


@pytest.fixture()
def repo(db):
    return SqlAlchemyTeamRepository(db)


@pytest.mark.parametrize(
    ("league_id", "owner_clause"),
    [(None, "team_members.match_id = 5"), (9, "team_members.league_id = 9")],
)
def test_team_query_filters_owner_and_user(repo, db, league_id, owner_clause):
    db.execute.return_value.all.return_value = []
    db.execute.return_value.first.return_value = None

    repo.get_match_team(5, league_id, 7)

    sql = literal_sql(db.execute.call_args_list[0].args[0])
    assert owner_clause in sql
    assert "team_members.user_id = 7" in sql  # nunca el equipo del rival


def test_starters_come_first_in_contract_order_then_substitutes_by_id(repo, db):
    db.execute.return_value.all.return_value = [
        row(6, 16, MemberRole.substitute),
        row(2, 12, MemberRole.defense),
        row(4, 14, MemberRole.substitute),
        row(3, 13, MemberRole.forward),
        row(1, 11, MemberRole.midfield),
        row(5, 15, MemberRole.substitute),
    ]
    db.execute.return_value.first.return_value = None

    team = repo.get_match_team(5, None, 7)

    assert [(member.role.value, member.player_id) for member in team.members] == [
        ("forward", 13),
        ("midfield", 11),
        ("defense", 12),
        ("substitute", 14),
        ("substitute", 15),
        ("substitute", 16),
    ]


def test_member_carries_its_current_behavior(repo, db):
    db.execute.return_value.all.return_value = [
        row(1, 11, MemberRole.forward, behavior_id=3, btype=BehaviorType.player_behavior)
    ]
    db.execute.return_value.first.return_value = None
    member = repo.get_match_team(5, None, 7).members[0]
    assert (member.behavior.id, member.behavior.name, member.behavior.type) == (
        3,
        "B3",
        BehaviorType.player_behavior,
    )


def test_friendly_has_no_dt_and_does_not_query_for_it(repo, db):
    db.execute.return_value.all.return_value = []
    team = repo.get_match_team(5, None, 7)
    assert team.coach_behavior is None
    assert db.execute.call_count == 1


def test_league_coach_is_read_from_the_participation(repo, db):
    db.execute.return_value.all.return_value = []
    db.execute.return_value.first.return_value = SimpleNamespace(
        behavior_id=9, behavior_name="DT", behavior_type=BehaviorType.coach_behavior
    )

    team = repo.get_match_team(5, 3, 7)

    assert (team.coach_behavior.id, team.coach_behavior.type) == (9, BehaviorType.coach_behavior)
    sql = literal_sql(db.execute.call_args_list[1].args[0])
    assert "league_participants.league_id = 3" in sql
    assert "league_participants.user_id = 7" in sql


def test_league_participation_without_dt_gives_none(repo, db):
    db.execute.return_value.all.return_value = []
    db.execute.return_value.first.return_value = None
    assert repo.get_match_team(5, 3, 7).coach_behavior is None
