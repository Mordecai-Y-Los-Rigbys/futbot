from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.domain.team_member import MemberRole
from app.models.behavior import Behavior
from app.models.player import Player
from app.models.substitution import Substitution
from app.models.team_member import TeamMember
from app.repositories.substitution_sqlalchemy import SqlAlchemySubstitutionRepository


def literal_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.fixture()
def db():
    return MagicMock(spec=Session)


@pytest.fixture()
def repo(db):
    return SqlAlchemySubstitutionRepository(db)


def test_apply_pending_locks_the_match_row(repo, db):
    db.execute.return_value.one_or_none.return_value = (1,)

    repo.apply_pending(7)

    assert "FOR UPDATE" in literal_sql(db.execute.call_args_list[0].args[0])


def test_apply_pending_sends_the_starter_to_the_bench_with_its_own_behavior(repo, db):
    starter = TeamMember(id=10, user_id=1, player_id=100, behavior_id=5, role=MemberRole.forward)
    bench_player = TeamMember(
        id=20, user_id=1, player_id=200, behavior_id=6, role=MemberRole.substitute
    )
    rows = {
        (TeamMember, 10): starter,
        (TeamMember, 20): bench_player,
        (Player, 200): Player(
            id=200, name="Suplente", power=60, agility=60, control=60, strength=60, speed=60
        ),
        (Behavior, 6): Behavior(id=6, code="codigo del suplente"),
    }
    db.execute.return_value.one_or_none.return_value = (1,)
    db.scalars.return_value.all.return_value = [
        Substitution(match_id=7, user_id=1, member_in_id=20, member_out_id=10)
    ]
    db.get.side_effect = lambda model, row_id: rows[(model, row_id)]

    swaps = repo.apply_pending(7)

    assert (starter.role, starter.behavior_id) == (MemberRole.substitute, 5)
    assert (bench_player.role, bench_player.behavior_id) == (MemberRole.forward, 6)
    assert swaps[0].incoming.behavior_code == "codigo del suplente"


def test_list_applied_by_match_reads_the_applied_table(repo, db):
    db.execute.return_value.all.return_value = []

    assert repo.list_applied_by_match(7) == []

    sql = literal_sql(db.execute.call_args.args[0])
    assert "FROM applied_substitutions" in sql
    assert "applied_substitutions.match_id = 7" in sql
    assert "ORDER BY applied_substitutions.user_id ASC" in sql


def test_list_by_match_filters_by_match_and_orders_by_team(repo, db):
    db.execute.return_value.all.return_value = []

    assert repo.list_by_match(7) == []

    sql = literal_sql(db.execute.call_args.args[0])
    assert "substitutions.match_id = 7" in sql
    assert "ORDER BY substitutions.user_id ASC" in sql


def test_upsert_uses_atomic_conflict_update(repo, db):
    repo.upsert(7, 1, 20, 10)
    sql = literal_sql(db.execute.call_args.args[0])
    assert "INSERT INTO substitutions" in sql
    assert "ON CONFLICT (match_id, user_id) DO UPDATE" in sql
    assert "member_in_id" in sql and "member_out_id" in sql
    db.commit.assert_called_once()
