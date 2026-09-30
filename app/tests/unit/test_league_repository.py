from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models.league import LeagueStatus
from app.repositories.league_sqlalchemy import SqlAlchemyLeagueRepository, _escape_like


def compiled(stmt):
    c = stmt.compile(dialect=postgresql.dialect())
    return str(c), c.params


def fake_league(id=1, status=LeagueStatus.preparation, created_at=None):
    return SimpleNamespace(
        id=id,
        name=f"Liga {id}",
        status=status,
        max_participants=8,
        private=False,
        created_at=created_at or datetime(2026, 1, 1),  # naive, como en SQLite/DateTime
        creator=SimpleNamespace(id=7, username="mgonzalez", club_name="Boca Juniors FC"),
    )


@pytest.fixture()
def db():
    mock = MagicMock(spec=Session)
    mock.scalar.return_value = 0
    mock.execute.return_value.all.return_value = []
    return mock


@pytest.fixture()
def repo(db):
    return SqlAlchemyLeagueRepository(db)


def list_stmt(db):
    return db.execute.call_args.args[0]


def count_stmt(db):
    return db.scalar.call_args.args[0]


# --- escape ------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, escaped",
    [
        ("boca", "boca"),
        ("100%", "100\\%"),
        ("a_b", "a\\_b"),
        ("a\\b", "a\\\\b"),
        ("%_\\", "\\%\\_\\\\"),
    ],
)
def test_escape_like(raw, escaped):
    assert _escape_like(raw) == escaped


# --- mapeo a DTO ---------------------------------------------------------

def test_maps_rows_to_dtos(repo, db):
    db.scalar.return_value = 1
    db.execute.return_value.all.return_value = [
        (fake_league(id=5, status=LeagueStatus.cancelled), 4)
    ]
    page = repo.list_page(name=None, offset=0, limit=50)
    item = page.items[0]
    assert page.total == 1
    assert item.id == 5
    assert item.status == "cancelled"
    assert item.participants_count == 4
    assert item.creator.username == "mgonzalez"
    assert item.creator.club_name == "Boca Juniors FC"


def test_naive_created_at_is_normalized_to_utc(repo, db):
    db.execute.return_value.all.return_value = [(fake_league(), 1)]
    item = repo.list_page(name=None, offset=0, limit=50).items[0]
    assert item.created_at.tzinfo is timezone.utc


def test_aware_created_at_is_kept(repo, db):
    aware = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.execute.return_value.all.return_value = [(fake_league(created_at=aware), 1)]
    assert repo.list_page(name=None, offset=0, limit=50).items[0].created_at == aware


def test_total_comes_from_the_count_query(repo, db):
    db.scalar.return_value = 120
    db.execute.return_value.all.return_value = [(fake_league(), 1)]
    assert repo.list_page(name=None, offset=100, limit=50).total == 120


# --- SQL generado --------------------------------------------------------

def test_orders_by_id_ascending(repo, db):
    repo.list_page(name=None, offset=0, limit=50)
    sql, _ = compiled(list_stmt(db))
    assert "ORDER BY leagues.id ASC" in sql


@pytest.mark.parametrize("offset", [0, 50, 100])
def test_applies_limit_and_offset(repo, db, offset):
    repo.list_page(name=None, offset=offset, limit=50)
    sql, params = compiled(list_stmt(db))
    assert "LIMIT" in sql and "OFFSET" in sql
    assert {offset, 50} <= set(params.values())


def test_count_query_has_no_pagination_or_order(repo, db):
    repo.list_page(name=None, offset=100, limit=50)
    sql, _ = compiled(count_stmt(db))
    assert "count(" in sql.lower()
    assert "LIMIT" not in sql and "OFFSET" not in sql and "ORDER BY" not in sql


def test_no_filter_when_name_is_absent(repo, db):
    repo.list_page(name=None, offset=0, limit=50)
    assert "ILIKE" not in compiled(list_stmt(db))[0]
    assert "ILIKE" not in compiled(count_stmt(db))[0]


def test_no_filter_when_name_is_empty(repo, db):
    repo.list_page(name="", offset=0, limit=50)
    assert "ILIKE" not in compiled(list_stmt(db))[0]


def test_filters_with_ilike_and_escape(repo, db):
    repo.list_page(name="boca", offset=0, limit=50)
    for stmt in (list_stmt(db), count_stmt(db)):  # misma condición en ambas
        sql, params = compiled(stmt)
        assert "ILIKE" in sql and "ESCAPE" in sql
        assert "%boca%" in params.values()


@pytest.mark.parametrize(
    "name, pattern",
    [
        ("100%", "%100\\%%"),
        ("a_b", "%a\\_b%"),
        ("a\\b", "%a\\\\b%"),
    ],
)
def test_special_characters_are_escaped_in_the_pattern(repo, db, name, pattern):
    repo.list_page(name=name, offset=0, limit=50)
    for stmt in (list_stmt(db), count_stmt(db)):
        assert pattern in compiled(stmt)[1].values()


def test_loads_creator_in_the_same_query(repo, db):
    repo.list_page(name=None, offset=0, limit=50)
    sql, _ = compiled(list_stmt(db))
    assert "JOIN users" in sql


def test_counts_participants_with_a_subquery(repo, db):
    repo.list_page(name=None, offset=0, limit=50)
    sql, _ = compiled(list_stmt(db))
    assert "league_participants" in sql
    assert "count(" in sql.lower()


@pytest.mark.parametrize("rows", [1, 50])
def test_always_two_statements_regardless_of_rows(repo, db, rows):
    """Sin N+1: la cantidad de queries no depende de cuántas ligas haya."""
    db.execute.return_value.all.return_value = [
        (fake_league(id=i), 1) for i in range(1, rows + 1)
    ]
    repo.list_page(name=None, offset=0, limit=50)
    assert db.scalar.call_count == 1
    assert db.execute.call_count == 1