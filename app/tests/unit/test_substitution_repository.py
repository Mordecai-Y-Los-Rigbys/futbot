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


def test_delete_first_per_team_deletes_the_min_id_of_each_team(repo, db):
    db.scalars.return_value = [4, 9]

    assert repo.delete_first_per_team(1) == 2

    stmt = db.execute.call_args.args[0]
    sql = literal_sql(stmt)
    assert "DELETE FROM substitutions" in sql
    assert "IN (4, 9)" in sql
    db.commit.assert_called_once()


def test_first_substitution_of_each_team_is_selected_by_min_id_per_user(repo, db):
    db.scalars.return_value = []

    repo.delete_first_per_team(7)

    sql = literal_sql(db.scalars.call_args.args[0])
    assert "min(substitutions.id)" in sql
    assert "JOIN team_members" in sql
    assert "substitutions.match_id = 7" in sql  # solo ese partido
    assert "GROUP BY team_members.user_id" in sql  # uno por equipo


def test_nothing_to_delete_skips_the_delete(repo, db):
    db.scalars.return_value = []

    assert repo.delete_first_per_team(1) == 0

    db.execute.assert_not_called()