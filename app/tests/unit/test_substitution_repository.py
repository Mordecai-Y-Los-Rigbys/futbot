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


def test_delete_by_match_deletes_the_substitutions_of_that_match_only(repo, db):
    db.execute.return_value.rowcount = 2

    assert repo.delete_by_match(7) == 2

    sql = literal_sql(db.execute.call_args.args[0])
    assert "DELETE FROM substitutions" in sql
    assert "substitutions.match_id = 7" in sql
    db.commit.assert_called_once()


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
