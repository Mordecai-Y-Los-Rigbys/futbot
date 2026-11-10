"""Tests de integración para las sustituciones

Las reglas que miran otras tablas las hace cumplir un trigger de Postgres,
así que no se pueden probar con el SQLite de los unit tests.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from app.api.ws_deps import get_match_runner
from app.domain.match import MatchStatus
from app.main import app
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.player import Player
from app.models.substitution import AppliedSubstitution, Substitution
from app.models.team_member import MemberRole, TeamMember
from app.repositories.substitution_sqlalchemy import SqlAlchemySubstitutionRepository
from app.repositories.team_sqlalchemy import SqlAlchemyTeamRepository
from app.services.match_progress import MatchProgress
from app.simulation.match_rules import Phase
from app.tests.integration.match_factories import add_league, add_team

pytestmark = pytest.mark.integration


def substitute(db, match, team, out_idx=0, in_idx=3):
    """Pide un cambio del equipo de `team`: sale team[out_idx] y entra
    team[in_idx]. Si el equipo ya tenía uno en el partido, lo reemplaza."""
    user_id = team[out_idx].user_id
    sub = db.get(Substitution, (match.id, user_id))
    if sub is None:
        sub = Substitution(
            match_id=match.id,
            user_id=user_id,
            member_in_id=team[in_idx].id,
            member_out_id=team[out_idx].id,
        )
        db.add(sub)
    else:
        sub.member_in_id = team[in_idx].id
        sub.member_out_id = team[out_idx].id
    db.commit()
    return sub


def by_user(db, match):
    rows = SqlAlchemySubstitutionRepository(db).list_by_match(match.id)
    return {r.user_id: r for r in rows}


def names_of(db, team, out_idx, in_idx):
    return (
        db.get(Player, team[out_idx].player_id).name,
        db.get(Player, team[in_idx].player_id).name,
    )


def assert_rejected(db, match, member_in, member_out, user_id=None):
    db.add(
        Substitution(
            match_id=match.id,
            user_id=member_in.user_id if user_id is None else user_id,
            member_in_id=member_in.id,
            member_out_id=member_out.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def remaining(db):
    db.expire_all()
    return {(s.match_id, s.user_id) for s in db.scalars(select(Substitution)).all()}


# --- caso válido ---


def test_valid_substitution_in_league_match(db_session, league_match):
    match, teams = league_match
    sub = substitute(db_session, match, teams[1])
    assert (sub.match_id, sub.user_id) == (match.id, 1)
    assert sub.member_in_id == teams[1][3].id
    assert sub.member_out_id == teams[1][0].id


def test_valid_substitution_in_friendly(db_session, friendly_match):
    match, teams = friendly_match
    substitute(db_session, match, teams[2])
    assert db_session.scalars(select(Substitution)).one().match_id == match.id


# --- una sola por equipo y partido ---


def test_requesting_again_replaces_the_previous_substitution(db_session, league_match):
    match, teams = league_match
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    substitute(db_session, match, teams[1], out_idx=1, in_idx=4)

    rows = db_session.scalars(select(Substitution)).all()
    assert len(rows) == 1
    assert rows[0].member_out_id == teams[1][1].id
    assert rows[0].member_in_id == teams[1][4].id


def test_a_second_row_for_the_same_team_and_match_is_rejected(db_session, league_match):
    match, teams = league_match
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)

    with pytest.raises(IntegrityError):
        db_session.execute(
            insert(Substitution).values(
                match_id=match.id,
                user_id=1,
                member_in_id=teams[1][4].id,
                member_out_id=teams[1][1].id,
            )
        )
        db_session.commit()
    db_session.rollback()


def test_each_team_has_its_own_substitution(db_session, league_match):
    match, teams = league_match
    substitute(db_session, match, teams[1])
    substitute(db_session, match, teams[2])
    assert remaining(db_session) == {(match.id, 1), (match.id, 2)}


def test_the_same_team_can_have_one_in_each_match(db_session, league_match):
    match, teams = league_match
    other = Match(
        league_id=match.league_id,
        user_1_id=1,
        user_2_id=2,
        status=MatchStatus.started,
        scheduled_at=datetime(2026, 1, 8, tzinfo=timezone.utc),
    )
    db_session.add(other)
    db_session.commit()

    substitute(db_session, match, teams[1])
    substitute(db_session, other, teams[1])
    assert remaining(db_session) == {(match.id, 1), (other.id, 1)}


# --- el partido debe estar en juego ---


@pytest.mark.parametrize("status", [MatchStatus.scheduled, MatchStatus.cancelled])
def test_match_not_started_is_rejected(db_session, league_match, status):
    match, teams = league_match
    match.status = status
    db_session.commit()
    assert_rejected(db_session, match, teams[1][3], teams[1][0])


def test_finished_match_is_rejected(db_session, league_match):
    match, teams = league_match
    match.status = MatchStatus.finished
    match.score_1, match.score_2 = 1, 0
    db_session.commit()
    assert_rejected(db_session, match, teams[1][3], teams[1][0])


def test_replacing_after_the_match_finished_is_rejected(db_session, league_match):
    match, teams = league_match
    sub = substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    match.status = MatchStatus.finished
    match.score_1, match.score_2 = 1, 0
    db_session.commit()

    sub.member_out_id, sub.member_in_id = teams[1][1].id, teams[1][4].id
    with pytest.raises(IntegrityError):  # el trigger también corre en UPDATE
        db_session.commit()
    db_session.rollback()


# --- mismo equipo ---


def test_members_of_different_teams_are_rejected(db_session, league_match):
    match, teams = league_match
    assert_rejected(db_session, match, teams[2][3], teams[1][0], user_id=1)


def test_same_member_in_and_out_is_rejected(db_session, league_match):
    match, teams = league_match
    assert_rejected(db_session, match, teams[1][0], teams[1][0])


def test_user_id_must_be_the_owner_of_the_members(db_session, league_match):
    match, teams = league_match
    # integrantes del equipo 1 cargados como cambio del equipo 2
    assert_rejected(db_session, match, teams[1][3], teams[1][0], user_id=2)


# --- el equipo debe ser del partido ---


def test_team_of_another_league_is_rejected(db_session, league_match, make_behaviors):
    match, _ = league_match
    other = add_league(db_session, name="Otra")
    db_session.add(LeagueParticipant(league_id=other.id, user_id=1))
    db_session.flush()
    foreign = add_team(db_session, 1, make_behaviors(1, ["x"], code="pass")[0], league_id=other.id)
    assert_rejected(db_session, match, foreign[3], foreign[0])


def test_team_of_another_friendly_is_rejected(db_session, friendly_match, make_behaviors):
    match, _ = friendly_match
    other = Match(user_1_id=1, user_2_id=2, status=MatchStatus.started)
    db_session.add(other)
    db_session.commit()
    foreign = add_team(db_session, 1, make_behaviors(1, ["y"], code="pass")[0], match_id=other.id)
    assert_rejected(db_session, match, foreign[3], foreign[0])


def test_team_of_a_user_not_in_the_match_is_rejected(
    db_session, league_match, make_user, make_behaviors
):
    match, _ = league_match
    make_user(3)
    db_session.add(LeagueParticipant(league_id=match.league_id, user_id=3))
    db_session.flush()
    outsider = add_team(
        db_session, 3, make_behaviors(3, ["z"], code="pass")[0], league_id=match.league_id
    )
    assert_rejected(db_session, match, outsider[3], outsider[0])


# --- cascade ---


def test_substitutions_are_deleted_with_the_match(db_session, friendly_match):
    match, teams = friendly_match
    substitute(db_session, match, teams[1])
    db_session.delete(match)
    db_session.commit()
    assert db_session.scalars(select(Substitution)).all() == []


# --- list_by_match ---


def test_list_by_match_returns_one_per_team_with_names(db_session, league_match):
    match, teams = league_match
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    substitute(db_session, match, teams[2], out_idx=1, in_idx=4)

    rows = by_user(db_session, match)

    assert set(rows) == {1, 2}
    for uid, (out_idx, in_idx) in {1: (0, 3), 2: (1, 4)}.items():
        assert (rows[uid].starter_name, rows[uid].substitute_name) == names_of(
            db_session, teams[uid], out_idx, in_idx
        )


def test_list_by_match_shows_the_latest_request(db_session, league_match):
    match, teams = league_match
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    substitute(db_session, match, teams[1], out_idx=2, in_idx=5)

    row = by_user(db_session, match)[1]
    assert (row.starter_name, row.substitute_name) == names_of(db_session, teams[1], 2, 5)


def test_list_by_match_keeps_names_after_roles_change(db_session, league_match):
    match, teams = league_match
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    expected = names_of(db_session, teams[1], 0, 3)

    # Se aplica el cambio: el que salió pasa a suplente y el que entró a titular.
    out_member, in_member = teams[1][0], teams[1][3]
    out_member.role, in_member.role = in_member.role, out_member.role
    db_session.commit()
    db_session.expire_all()
    assert out_member.role == MemberRole.substitute and in_member.role == MemberRole.forward

    row = by_user(db_session, match)[1]
    # starter = member_out_id y substitute = member_in_id, sin importar el rol actual.
    assert (row.starter_name, row.substitute_name) == expected


def test_list_by_match_ignores_other_matches_and_empty_teams(db_session, league_match):
    match, teams = league_match
    other = Match(
        league_id=match.league_id,
        user_1_id=1,
        user_2_id=2,
        status=MatchStatus.started,
        scheduled_at=datetime(2026, 1, 8, tzinfo=timezone.utc),
    )
    db_session.add(other)
    db_session.commit()
    substitute(db_session, other, teams[1], out_idx=1, in_idx=4)
    substitute(db_session, other, teams[2], out_idx=1, in_idx=4)

    repo = SqlAlchemySubstitutionRepository(db_session)
    assert repo.list_by_match(match.id) == []  # el partido objetivo no tiene cambios

    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    rows = by_user(db_session, match)
    assert set(rows) == {1}  # el equipo 2 no aparece y no se cuelan los del otro partido
    assert (rows[1].starter_name, rows[1].substitute_name) == names_of(db_session, teams[1], 0, 3)


# --- apply_pending (empieza cada pausa) ---


def applied_by_user(db, match):
    rows = SqlAlchemySubstitutionRepository(db).list_applied_by_match(match.id)
    return {r.user_id: r for r in rows}


def roles_of(db, team):
    db.expire_all()
    return {m.player_id: db.get(TeamMember, m.id).role for m in team}


def test_apply_pending_swaps_the_roles_and_returns_the_incoming_player(db_session, league_match):
    match, teams = league_match
    out, inn = teams[1][0], teams[1][3]  # sale el delantero, entra un suplente
    out_player, in_player = out.player_id, inn.player_id
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)

    swaps = SqlAlchemySubstitutionRepository(db_session).apply_pending(match.id)

    assert len(swaps) == 1
    assert swaps[0].club == "club1"
    assert swaps[0].out_player_id == out_player
    assert swaps[0].incoming.player_id == in_player
    assert swaps[0].incoming.role is MemberRole.forward  # toma el rol del que sale
    assert swaps[0].incoming.behavior_code == "pass"
    roles = roles_of(db_session, teams[1])
    assert roles[out_player] is MemberRole.substitute
    assert roles[in_player] is MemberRole.forward
    # el cambio persiste: es el equipo de la liga
    starters = SqlAlchemyTeamRepository(db_session).get_starters(match.id, match.league_id, 1)
    assert in_player in {r.player_id for r in starters}
    assert out_player not in {r.player_id for r in starters}


def test_the_starter_that_leaves_keeps_its_behavior_on_the_bench(
    db_session, league_match, make_behaviors
):
    match, teams = league_match
    starter, bench_player = teams[1][0], teams[1][3]
    bench_behavior = make_behaviors(1, ["suplente"])[0]
    bench_player.behavior_id = bench_behavior.id
    db_session.commit()
    starter_behavior_id = starter.behavior_id
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)

    SqlAlchemySubstitutionRepository(db_session).apply_pending(match.id)

    db_session.expire_all()
    assert (starter.role, starter.behavior_id) == (MemberRole.substitute, starter_behavior_id)
    assert (bench_player.role, bench_player.behavior_id) == (MemberRole.forward, bench_behavior.id)


def test_after_three_substitutions_the_team_has_three_starters_and_three_substitutes(
    db_session, league_match
):
    match, teams = league_match
    repo = SqlAlchemySubstitutionRepository(db_session)
    for out_idx, in_idx in ((0, 3), (1, 4), (2, 5)):
        substitute(db_session, match, teams[1], out_idx=out_idx, in_idx=in_idx)
        repo.apply_pending(match.id)

    roles = roles_of(db_session, teams[1])
    team = teams[1]
    assert roles == {
        team[0].player_id: MemberRole.substitute,
        team[1].player_id: MemberRole.substitute,
        team[2].player_id: MemberRole.substitute,
        team[3].player_id: MemberRole.forward,
        team[4].player_id: MemberRole.midfield,
        team[5].player_id: MemberRole.defense,
    }


def test_apply_pending_moves_the_pending_to_applied(db_session, league_match):
    match, teams = league_match
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    names = names_of(db_session, teams[1], 0, 3)

    SqlAlchemySubstitutionRepository(db_session).apply_pending(match.id)

    assert by_user(db_session, match) == {}  # ya no está pendiente
    applied = applied_by_user(db_session, match)
    assert (applied[1].starter_name, applied[1].substitute_name) == names


def test_each_team_applies_its_own_substitution(db_session, league_match):
    match, teams = league_match
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    substitute(db_session, match, teams[2], out_idx=1, in_idx=4)

    swaps = SqlAlchemySubstitutionRepository(db_session).apply_pending(match.id)

    assert {s.club for s in swaps} == {"club1", "club2"}
    assert set(applied_by_user(db_session, match)) == {1, 2}


def test_a_new_pause_replaces_the_previous_applied_ones(db_session, league_match):
    match, teams = league_match
    repo = SqlAlchemySubstitutionRepository(db_session)
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    repo.apply_pending(match.id)
    assert set(applied_by_user(db_session, match)) == {1}

    substitute(db_session, match, teams[2], out_idx=1, in_idx=4)  # solo pide el equipo 2
    repo.apply_pending(match.id)

    assert set(applied_by_user(db_session, match)) == {2}  # el equipo 1 queda sin cambio


def test_a_pause_without_pending_clears_the_applied_ones(db_session, league_match):
    match, teams = league_match
    repo = SqlAlchemySubstitutionRepository(db_session)
    substitute(db_session, match, teams[1])
    repo.apply_pending(match.id)

    assert repo.apply_pending(match.id) == []
    assert applied_by_user(db_session, match) == {}


def test_a_request_made_during_the_pause_stays_pending_for_the_next_one(db_session, league_match):
    match, teams = league_match
    repo = SqlAlchemySubstitutionRepository(db_session)
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    repo.apply_pending(match.id)

    substitute(db_session, match, teams[1], out_idx=1, in_idx=4)  # PUT durante la pausa

    assert set(by_user(db_session, match)) == {1}  # pendiente
    applied = applied_by_user(db_session, match)[1]  # sigue mostrándose la aplicada
    assert (applied.starter_name, applied.substitute_name) == names_of(db_session, teams[1], 0, 3)


def test_an_invalid_pending_substitution_is_discarded(db_session, league_match):
    match, teams = league_match
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)
    # Antes de la pausa el suplente que iba a entrar pasó a ser titular (y el medio, suplente).
    teams[1][3].role, teams[1][1].role = MemberRole.midfield, MemberRole.substitute
    db_session.commit()

    assert SqlAlchemySubstitutionRepository(db_session).apply_pending(match.id) == []

    assert by_user(db_session, match) == {}  # se descartó, no queda pendiente
    assert applied_by_user(db_session, match) == {}
    assert roles_of(db_session, teams[1])[teams[1][0].player_id] is MemberRole.forward


def test_apply_pending_does_not_touch_other_matches(db_session, league_match):
    match, teams = league_match
    other = Match(
        league_id=match.league_id,
        user_1_id=1,
        user_2_id=2,
        status=MatchStatus.started,
        scheduled_at=datetime(2026, 1, 8, tzinfo=timezone.utc),
    )
    db_session.add(other)
    db_session.commit()
    substitute(db_session, match, teams[1])
    substitute(db_session, other, teams[1])
    other_id = other.id

    SqlAlchemySubstitutionRepository(db_session).apply_pending(match.id)

    assert remaining(db_session) == {(other_id, 1)}


def test_applied_substitutions_are_deleted_with_the_match(db_session, friendly_match):
    match, teams = friendly_match
    substitute(db_session, match, teams[1])
    SqlAlchemySubstitutionRepository(db_session).apply_pending(match.id)
    db_session.delete(match)
    db_session.commit()
    assert db_session.scalars(select(AppliedSubstitution)).all() == []


def test_endpoint_outsider_is_403_and_not_started_is_409(
    login, db_session, make_user, friendly_match
):
    match, _ = friendly_match
    make_user(3)
    assert login(3).get(f"/matches/{match.id}/substitutions").status_code == 403
    match.status = MatchStatus.finished
    match.score_1, match.score_2 = 1, 0
    db_session.commit()
    r = login(1).get(f"/matches/{match.id}/substitutions")
    assert (r.status_code, r.json()["code"]) == (409, "matchNotStarted")


def test_endpoint_returns_the_substitution_of_each_team(login, friendly_match, db_session):
    match, teams = friendly_match
    substitute(db_session, match, teams[1], out_idx=0, in_idx=3)

    r = login(2).get(f"/matches/{match.id}/substitutions")

    assert r.status_code == 200
    assert r.json()["club2"] is None
    assert r.json()["club1"] == dict(
        zip(("starterName", "substituteName"), names_of(db_session, teams[1], 0, 3))
    )


# --- PUT /matches/{id}/substitutions --------------------------------------------


class FakeProgress:
    """El partido se está jugando en el 1.er período de 4 (le quedan 3 pausas)."""

    def progress(self, match_id):
        return MatchProgress(Phase.PLAYING, period=1, periods=4)


@pytest.fixture()
def running():
    app.dependency_overrides[get_match_runner] = lambda: FakeProgress()
    yield
    app.dependency_overrides.pop(get_match_runner, None)


def put_substitution(api, match, starter, substitute):
    body = {"starterId": starter.player_id, "substituteId": substitute.player_id}
    return api.put(f"/matches/{match.id}/substitutions", json=body)


def test_put_endpoint_persists_and_replaces_the_team_pending_substitution(
    login, friendly_match, db_session, running
):
    match, teams = friendly_match
    api = login(1)

    assert put_substitution(api, match, teams[1][0], teams[1][3]).status_code == 204
    assert put_substitution(api, match, teams[1][1], teams[1][4]).status_code == 204

    rows = db_session.scalars(select(Substitution).where(Substitution.match_id == match.id)).all()
    assert len(rows) == 1
    assert rows[0].member_out_id == teams[1][1].id
    assert rows[0].member_in_id == teams[1][4].id

    response = api.get(f"/matches/{match.id}/substitutions")
    assert response.json()["club1"] == dict(
        zip(("starterName", "substituteName"), names_of(db_session, teams[1], 1, 4))
    )


def field_errors(response):
    assert response.status_code == 400
    return [(error["field"], error["reason"]) for error in response.json()["errors"]]


def test_put_starter_of_the_rival_is_not_starter(login, friendly_match, running):
    match, teams = friendly_match
    response = put_substitution(login(1), match, teams[2][0], teams[1][3])
    assert field_errors(response) == [("starterId", "notStarter")]


def test_put_starter_as_substitute_is_not_substitute(login, friendly_match, running):
    match, teams = friendly_match
    response = put_substitution(login(1), match, teams[1][0], teams[1][1])
    assert field_errors(response) == [("substituteId", "notSubstitute")]


def test_put_user_outside_the_match_is_403(login, make_user, friendly_match, running):
    match, teams = friendly_match
    make_user(3)
    response = put_substitution(login(3), match, teams[1][0], teams[1][3])
    assert (response.status_code, response.json()["code"]) == (403, None)


def test_put_scheduled_match_is_409(login, friendly_match, db_session, running):
    match, teams = friendly_match
    match.status = MatchStatus.scheduled
    db_session.commit()
    response = put_substitution(login(1), match, teams[1][0], teams[1][3])
    assert (response.status_code, response.json()["code"]) == (409, "matchNotStarted")
