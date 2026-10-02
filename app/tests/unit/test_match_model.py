"""Tests del mapeo del modelo Match. No usan ninguna base de datos: inspeccionan
la metadata de SQLAlchemy y el DDL que se generaría para Postgres. El
comportamiento real de los CHECK se prueba en
integration/test_match_constraints.py."""
import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app import models  # noqa: F401  (registra todos los modelos)
from app.models.league import League
from app.models.match import Match, MatchStatus
from app.models.user import User

TABLE = Match.__table__


# --- tabla y columnas -----------------------------------------------------------

def test_table_name():
    assert TABLE.name == "matches"


def test_columns():
    assert set(TABLE.c.keys()) == {
        "id", "league_id", "home_user_id", "away_user_id",
        "status", "scheduled_at", "home_score", "away_score",
    }


def test_primary_key_is_id():
    assert [c.name for c in TABLE.primary_key.columns] == ["id"]


@pytest.mark.parametrize(
    "column, nullable",
    [
        ("league_id", True),      # NULL = partido amistoso
        ("home_user_id", False),
        ("away_user_id", True),   # NULL = amistoso esperando rival
        ("status", False),
        ("scheduled_at", True),   # NULL = amistoso (sin fecha programada)
        ("home_score", True),     # NULL hasta que el partido termina
        ("away_score", True),
    ],
)
def test_nullability(column, nullable):
    assert TABLE.c[column].nullable is nullable


# --- estado ---------------------------------------------------------------------

def test_status_values_match_the_openapi_contract():
    enum_type = TABLE.c.status.type
    assert enum_type.name == "match_status"
    assert list(enum_type.enums) == ["scheduled", "started", "finished"]


def test_status_is_a_string_enum():
    assert MatchStatus.finished == "finished"
    assert MatchStatus("started") is MatchStatus.started


def test_new_matches_default_to_scheduled():
    assert TABLE.c.status.default.arg is MatchStatus.scheduled


# --- claves foráneas e índices --------------------------------------------------------

def test_foreign_keys():
    fks = {
        (fk.parent.name, fk.column.table.name, fk.column.name, fk.ondelete)
        for fk in TABLE.foreign_keys
    }
    assert fks == {
        ("league_id", "leagues", "id", "CASCADE"),
        ("home_user_id", "users", "id", None),
        ("away_user_id", "users", "id", None),
    }


def test_lookup_columns_are_indexed():
    # Las consultas por usuario ("¿ya está jugando?", partidos del usuario) y
    # por liga (fixture, partidos en curso) filtran por estas columnas.
    indexed = {c.name for idx in TABLE.indexes for c in idx.columns}
    assert indexed == {"league_id", "home_user_id", "away_user_id"}


# --- invariantes (CHECK) -----------------------------------------------------------------

EXPECTED_CHECKS = {
    "ck_matches_distinct_clubs": "away_user_id IS NULL OR home_user_id <> away_user_id",
    "ck_matches_started_has_rival": "status = 'scheduled' OR away_user_id IS NOT NULL",
    "ck_matches_scores_both_or_none": "(home_score IS NULL) = (away_score IS NULL)",
    "ck_matches_result_iff_finished": "(status = 'finished') = (home_score IS NOT NULL)",
    "ck_matches_scores_non_negative": "home_score >= 0 AND away_score >= 0",
    "ck_matches_league_match_has_date": "league_id IS NULL OR scheduled_at IS NOT NULL",
}


def checks():
    return {
        c.name: str(c.sqltext)
        for c in TABLE.constraints
        if isinstance(c, CheckConstraint)
    }


def test_check_constraints():
    assert checks() == EXPECTED_CHECKS


def test_ddl_for_postgres_includes_every_check():
    ddl = str(CreateTable(TABLE).compile(dialect=postgresql.dialect()))
    assert ddl.startswith("\nCREATE TABLE matches")
    for name, sqltext in EXPECTED_CHECKS.items():
        assert f"CONSTRAINT {name} CHECK ({sqltext})" in ddl


# --- relaciones ----------------------------------------------------------------------------

def test_mappers_configure_without_ambiguity():
    # Con dos FK a users, una relación sin foreign_keys explícito rompe acá.
    configure_mappers()


@pytest.mark.parametrize(
    "name, target, local_column",
    [
        ("league", League, "league_id"),
        ("home_user", User, "home_user_id"),
        ("away_user", User, "away_user_id"),
    ],
)
def test_relationships(name, target, local_column):
    rel = sa_inspect(Match).relationships[name]
    assert rel.mapper.class_ is target
    assert {c.name for c in rel.local_columns} == {local_column}


# --- instancias en memoria -------------------------------------------------------------------

def test_friendly_waiting_for_a_rival_can_be_built_with_only_the_creator():
    match = Match(home_user_id=1)
    assert match.league_id is None
    assert match.away_user_id is None
    assert match.home_score is None and match.away_score is None