from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

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

