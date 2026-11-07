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


def test_list_by_match_filters_by_match_and_applied_and_orders_by_team(repo, db):
    db.execute.return_value.all.return_value = []

    assert repo.list_by_match(7, applied=True) == []

    sql = literal_sql(db.execute.call_args.args[0])
    assert "substitutions.match_id = 7" in sql
    assert "substitutions.applied IS true" in sql
    assert "ORDER BY substitutions.user_id ASC" in sql


def test_delete_applied_by_match_deletes_only_applied_rows_of_that_match(repo, db):
    db.execute.return_value.rowcount = 2

    assert repo.delete_applied_by_match(7) == 2

    sql = literal_sql(db.execute.call_args.args[0])
    assert "DELETE FROM substitutions" in sql
    assert "substitutions.match_id = 7" in sql
    assert "substitutions.applied IS true" in sql
    db.commit.assert_called_once()

def test_upsert_only_touches_the_pending_row(repo, db):
    repo.upsert(7, 1, 20, 10)
    sql = literal_sql(db.execute.call_args.args[0])
    assert "INSERT INTO substitutions" in sql
    assert "ON CONFLICT (match_id, user_id, applied) DO UPDATE" in sql
    assert "member_in_id" in sql and "member_out_id" in sql
    db.commit.assert_called_once()


def test_upsert_rolls_back_and_reraises_on_integrity_error(repo, db):
    db.commit.side_effect = IntegrityError("stmt", {}, Exception("x"))
    with pytest.raises(IntegrityError):
        repo.upsert(7, 1, 20, 10)
    db.rollback.assert_called_once()
