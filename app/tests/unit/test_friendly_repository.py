from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models.match import MatchStatus
from app.repositories.friendly_sqlalchemy import SqlAlchemyFriendlyRepository, _escape_like
from app.repositories.match_expiry_sqlalchemy import SqlAlchemyMatchExpiryRepository

USER_ID = 7


def compiled(stmt):
    c = stmt.compile(dialect=postgresql.dialect())
    return str(c), c.params


def fake_match(id=1, name="Amistoso", created_at=None):
    return SimpleNamespace(
        id=id,
        name=name,
        status=MatchStatus.scheduled,
        created_at=created_at or datetime(2026, 1, 1),
        user_1=SimpleNamespace(id=3, username="mgonzalez", club_name="Boca Juniors FC"),
    )


@pytest.fixture()
def db():
    mock = MagicMock(spec=Session)
    mock.scalar.return_value = 0
    mock.scalars.return_value.all.return_value = []
    return mock


@pytest.fixture()
def repo(db):
    return SqlAlchemyFriendlyRepository(db)


def list_page(repo, name=None, offset=0, limit=50, user_id=USER_ID):
    return repo.list_waiting_page(
        exclude_user_id=user_id, name=name, offset=offset, limit=limit
    )


def list_stmt(db):
    return db.scalars.call_args.args[0]


def count_stmt(db):
    return db.scalar.call_args.args[0]


# --- escape ------------------------------------------------------------------------------

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


# --- mapeo a DTO -----------------------------------------------------------------------------

def test_maps_rows_to_dtos(repo, db):
    db.scalar.return_value = 1
    db.scalars.return_value.all.return_value = [fake_match(id=5)]
    page = list_page(repo)
    item = page.items[0]
    assert page.total == 1
    assert item.id == 5
    assert item.name == "Amistoso"
    assert item.status == "scheduled"
    assert item.club1.id == 3
    assert item.club1.username == "mgonzalez"
    assert item.club1.club_name == "Boca Juniors FC"


def test_match_without_name_is_mapped(repo, db):
    db.scalars.return_value.all.return_value = [fake_match(name=None)]
    assert list_page(repo).items[0].name is None


def test_naive_created_at_is_normalized_to_utc(repo, db):
    db.scalars.return_value.all.return_value = [fake_match()]
    assert list_page(repo).items[0].created_at.tzinfo is timezone.utc


def test_aware_created_at_is_kept(repo, db):
    aware = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.scalars.return_value.all.return_value = [fake_match(created_at=aware)]
    assert list_page(repo).items[0].created_at == aware


def test_total_comes_from_the_count_query(repo, db):
    db.scalar.return_value = 120
    db.scalars.return_value.all.return_value = [fake_match()]
    assert list_page(repo, offset=100).total == 120


# --- SQL generado ---------------------------------------------------------------------------------

def test_orders_by_id_ascending(repo, db):
    list_page(repo)
    assert "ORDER BY matches.id ASC" in compiled(list_stmt(db))[0]


@pytest.mark.parametrize("offset", [0, 50, 100])
def test_applies_limit_and_offset(repo, db, offset):
    list_page(repo, offset=offset)
    sql, params = compiled(list_stmt(db))
    assert "LIMIT" in sql and "OFFSET" in sql
    assert {offset, 50} <= set(params.values())


def test_count_query_has_no_pagination_or_order(repo, db):
    list_page(repo, offset=100)
    sql, _ = compiled(count_stmt(db))
    assert "count(" in sql.lower()
    assert "LIMIT" not in sql and "OFFSET" not in sql and "ORDER BY" not in sql


def test_filters_only_friendlies_waiting_for_a_rival(repo, db):
    list_page(repo)
    for stmt in (list_stmt(db), count_stmt(db)):
        sql, params = compiled(stmt)
        assert "matches.league_id IS NULL" in sql
        assert "matches.user_2_id IS NULL" in sql
        assert "matches.status" in sql
        assert MatchStatus.scheduled in params.values()


def test_excludes_the_logged_user_in_both_queries(repo, db):
    list_page(repo, user_id=42)
    for stmt in (list_stmt(db), count_stmt(db)):
        sql, params = compiled(stmt)
        assert "matches.user_1_id !=" in sql
        assert 42 in params.values()


def test_reuses_the_is_waiting_friendly_condition(repo, db, monkeypatch):
    original = SqlAlchemyMatchExpiryRepository.is_waiting_friendly
    calls = []

    def spy():
        calls.append(1)
        return original()

    monkeypatch.setattr(
        SqlAlchemyMatchExpiryRepository, "is_waiting_friendly", staticmethod(spy)
    )
    list_page(repo)
    assert calls


def test_no_name_filter_when_name_is_absent(repo, db):
    list_page(repo, name=None)
    assert "ILIKE" not in compiled(list_stmt(db))[0]
    assert "ILIKE" not in compiled(count_stmt(db))[0]


def test_no_name_filter_when_name_is_empty(repo, db):
    list_page(repo, name="")
    assert "ILIKE" not in compiled(list_stmt(db))[0]


def test_filters_by_name_with_ilike_and_escape(repo, db):
    list_page(repo, name="boca")
    for stmt in (list_stmt(db), count_stmt(db)):
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
    list_page(repo, name=name)
    for stmt in (list_stmt(db), count_stmt(db)):
        assert pattern in compiled(stmt)[1].values()


def test_loads_creator_in_the_same_query(repo, db):
    list_page(repo)
    assert "JOIN users" in compiled(list_stmt(db))[0]


@pytest.mark.parametrize("rows", [1, 50])
def test_always_two_statements_regardless_of_rows(repo, db, rows):
    db.scalars.return_value.all.return_value = [fake_match(id=i) for i in range(1, rows + 1)]
    list_page(repo)
    assert db.scalar.call_count == 1
    assert db.scalars.call_count == 1
    assert db.execute.call_count == 0