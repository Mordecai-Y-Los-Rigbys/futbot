from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories.substitution_sqlalchemy import SqlAlchemySubstitutionRepository


def literal_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.fixture()
def db():
    return MagicMock(spec=Session)


@pytest.fixture()
def repo(db):
    return SqlAlchemySubstitutionRepository(db)


def test_apply_pending_for_a_nonexistent_match_changes_nothing(repo, db):
    db.execute.return_value.one_or_none.return_value = None

    assert repo.apply_pending(7) == []

    db.commit.assert_not_called()
    db.add.assert_not_called()


def test_apply_pending_locks_the_match_row(repo, db):
    db.execute.return_value.one_or_none.return_value = None

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

def test_upsert_replaces_the_pending_row_of_the_team(repo, db):
    repo.upsert(7, 1, 20, 10)
    sql = literal_sql(db.execute.call_args.args[0])
    assert "INSERT INTO substitutions" in sql
    assert "ON CONFLICT (match_id, user_id) DO UPDATE" in sql
    assert "member_in_id" in sql and "member_out_id" in sql
    db.commit.assert_called_once()


def test_upsert_rolls_back_and_reraises_on_integrity_error(repo, db):
    db.commit.side_effect = IntegrityError("stmt", {}, Exception("x"))
    with pytest.raises(IntegrityError):
        repo.upsert(7, 1, 20, 10)
    db.rollback.assert_called_once()
