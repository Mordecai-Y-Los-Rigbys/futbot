from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.repositories.team_sqlalchemy import SqlAlchemyTeamRepository


def literal_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


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
@pytest.mark.parametrize(
    ("substitute", "role_clause"),
    [(False, "team_members.role != 'substitute'"), (True, "team_members.role = 'substitute'")],
)
def test_get_member_id_filters_owner_user_player_and_role(
    repo, db, league_id, owner_clause, substitute, role_clause
):
    db.scalar.return_value = 123

    assert repo.get_member_id(5, league_id, 7, 10, substitute=substitute) == 123

    sql = literal_sql(db.scalar.call_args.args[0])
    assert owner_clause in sql
    assert "team_members.user_id = 7" in sql
    assert "team_members.player_id = 10" in sql
    assert role_clause in sql
