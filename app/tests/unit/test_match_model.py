"""Tests del mapeo del modelo Match. No usan ninguna base de datos: inspeccionan
la metadata de SQLAlchemy y el DDL que se generaría para Postgres. El
comportamiento real de los CHECK se prueba en
integration/test_match_constraints.py."""
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app import models  # noqa: F401  (registra todos los modelos)
from app.domain.match import MatchStatus
from app.models.match import Match

TABLE = Match.__table__


def test_status_values_match_the_openapi_contract():
    enum_type = TABLE.c.status.type
    assert enum_type.name == "match_status"
    assert list(enum_type.enums) == [MatchStatus.scheduled, MatchStatus.started, MatchStatus.finished, MatchStatus.cancelled]


def test_mappers_configure_without_ambiguity():
    # Con dos FK a users, una relación sin foreign_keys explícito rompe acá.
    configure_mappers()


def test_ddl_for_postgres_includes_every_check():
    expected_checks = {
        "ck_matches_distinct_clubs": "user_2_id IS NULL OR user_1_id <> user_2_id",
        "ck_matches_started_has_rival": "status = 'scheduled' OR user_2_id IS NOT NULL",
        "ck_matches_scores_both_or_none": "(score_1 IS NULL) = (score_2 IS NULL)",
        "ck_matches_result_iff_finished": "(status = 'finished') = (score_1 IS NOT NULL)",
        "ck_matches_scores_non_negative": "score_1 >= 0 AND score_2 >= 0",
        "ck_matches_league_match_has_date": "league_id IS NULL OR scheduled_at IS NOT NULL",
        "ck_matches_league_match_has_rival": "league_id IS NULL OR user_2_id IS NOT NULL",
    }
    ddl = str(CreateTable(TABLE).compile(dialect=postgresql.dialect()))
    assert ddl.startswith("\nCREATE TABLE matches")
    for name, sqltext in expected_checks.items():
        assert f"CONSTRAINT {name} CHECK ({sqltext})" in ddl


def test_friendly_waiting_for_a_rival_can_be_built_with_only_the_creator():
    match = Match(user_1_id=1)
    assert match.league_id is None
    assert match.user_2_id is None
    assert match.score_1 is None and match.score_2 is None