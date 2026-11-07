"""GET /matches/{id}/team contra la base real (Postgres), con sesiones reales."""

from datetime import datetime, timezone

import pytest

from app.domain.behavior import BehaviorType
from app.domain.match import MatchStatus
from app.models.behavior import Behavior
from app.models.league import League, LeagueStatus
from app.models.league_participant import LeagueParticipant
from app.models.match import Match
from app.models.player import Player
from app.models.substitution import Substitution
from app.models.team_member import MemberRole, TeamMember
from app.repositories.substitution_sqlalchemy import SqlAlchemySubstitutionRepository

pytestmark = pytest.mark.integration

ROLES = [MemberRole.forward, MemberRole.midfield, MemberRole.defense] + [MemberRole.substitute] * 3
ROLE_NAMES = [r.value for r in ROLES]


def add_team(db, user_id, behavior, **owner):
    """6 jugadores y su equipo en `owner` (league_id=... o match_id=...)."""
    players = [
        Player(
            user_id=user_id,
            name=f"u{user_id}p{i}",
            power=60,
            agility=60,
            control=60,
            strength=60,
            speed=60,
        )
        for i in range(6)
    ]
    db.add_all(players)
    db.commit()
    members = [
        TeamMember(user_id=user_id, player_id=p.id, behavior_id=behavior.id, role=role, **owner)
        for p, role in zip(players, ROLES)
    ]
    db.add_all(members)
    db.commit()
    return members


def add_coach(db, user_id, name="DT"):
    coach = Behavior(user_id=user_id, name=name, code="pass", type=BehaviorType.coach_behavior)
    db.add(coach)
    db.commit()
    return coach


@pytest.fixture()
def league_match(db_session, make_user, make_behaviors):
    """Partido de liga `started` entre 1 y 2. El usuario 1 tiene DT; el 2, no."""
    make_user(1), make_user(2), make_user(3)
    league = League(
        name="L",
        creator_id=1,
        status=LeagueStatus.started,
        min_participants=3,
        max_participants=8,
        match_duration=2,
        private=False,
    )
    db_session.add(league)
    db_session.flush()
    coach = add_coach(db_session, 1)
    teams = {}
    for uid in (1, 2):
        db_session.add(
            LeagueParticipant(
                league_id=league.id,
                user_id=uid,
                coach_behavior_id=coach.id if uid == 1 else None,
            )
        )
        db_session.flush()
        behavior = make_behaviors(uid, [f"pb{uid}"], code="pass")[0]
        teams[uid] = add_team(db_session, uid, behavior, league_id=league.id)
    match = Match(
        league_id=league.id,
        user_1_id=1,
        user_2_id=2,
        status=MatchStatus.started,
        scheduled_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(match)
    db_session.commit()
    return match, teams, coach


@pytest.fixture()
def friendly_match(db_session, make_user, make_behaviors):
    make_user(1), make_user(2), make_user(3)
    match = Match(user_1_id=1, user_2_id=2, status=MatchStatus.started)
    db_session.add(match)
    db_session.commit()
    teams = {
        uid: add_team(
            db_session, uid, make_behaviors(uid, [f"fb{uid}"], code="pass")[0], match_id=match.id
        )
        for uid in (1, 2)
    }
    return match, teams


def get_team(api, match_id):
    return api.get(f"/matches/{match_id}/team")


# --- 401 / 404 ----------------------------------------------------------------


def test_without_cookie_is_401(client, friendly_match):
    match, _ = friendly_match
    r = client.get(f"/matches/{match.id}/team")
    assert r.status_code == 401 and r.json()["code"] is None


def test_unknown_match_is_404(login_as, db_session, make_user):
    api = login_as(make_user(1))
    assert get_team(api, 999999).status_code == 404


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_id_is_404(login_as, make_user, bad):
    api = login_as(make_user(1))
    assert get_team(api, bad).status_code == 404


def test_401_wins_over_404(client):
    assert client.get("/matches/999999/team").status_code == 401


# --- 403 ----------------------------------------------------------------------


def test_user_who_does_not_play_is_403(login_as, friendly_match, make_user):
    match, _ = friendly_match
    r = get_team(login_as(make_user(3)), match.id)
    assert r.status_code == 403
    assert r.json()["code"] == "notAPlayerInMatch"


def test_league_spectator_with_access_is_403(login_as, league_match, make_user):
    match, _, _ = league_match  # liga pública: el usuario 3 puede ver el partido
    r = get_team(login_as(make_user(3)), match.id)
    assert r.status_code == 403
    assert r.json()["code"] == "notAPlayerInMatch"


def test_stranger_cannot_take_the_free_rival_slot(login_as, db_session, make_user, make_behaviors):
    make_user(1), make_user(3)
    match = Match(user_1_id=1, name="Amistoso", status=MatchStatus.scheduled)
    db_session.add(match)
    db_session.commit()
    add_team(db_session, 1, make_behaviors(1, ["b"], code="pass")[0], match_id=match.id)
    r = get_team(login_as(make_user(3)), match.id)
    assert (r.status_code, r.json()["code"]) == (403, "notAPlayerInMatch")


# --- 200 ----------------------------------------------------------------------


@pytest.mark.parametrize("uid", [1, 2])
def test_player_gets_own_six_members_starters_first(login_as, friendly_match, make_user, uid):
    match, teams = friendly_match
    r = get_team(login_as(make_user(uid)), match.id)
    assert r.status_code == 200
    body = r.json()
    assert [m["role"] for m in body["members"]] == ROLE_NAMES
    assert {m["playerId"] for m in body["members"]} == {t.player_id for t in teams[uid]}
    for m in body["members"]:
        assert set(m) == {"playerId", "name", "role", "behavior"}
        assert set(m["behavior"]) == {"id", "name", "type"}
        assert m["behavior"]["type"] == "playerBehavior"
        assert m["name"].startswith(f"u{uid}p")  # nunca los del rival


def test_never_returns_the_rival_team(login_as, friendly_match, make_user):
    match, teams = friendly_match
    body = get_team(login_as(make_user(1)), match.id).json()
    rival_players = {t.player_id for t in teams[2]}
    assert rival_players.isdisjoint(m["playerId"] for m in body["members"])


def test_league_match_uses_the_league_team_and_the_dt(login_as, league_match, make_user):
    match, teams, coach = league_match
    body = get_team(login_as(make_user(1)), match.id).json()
    assert {m["playerId"] for m in body["members"]} == {t.player_id for t in teams[1]}
    assert body["coachBehavior"] == {"id": coach.id, "name": "DT", "type": "coachBehavior"}


def test_coach_behavior_is_null_when_the_team_has_no_dt(login_as, league_match, make_user):
    match, _, _ = league_match
    body = get_team(login_as(make_user(2)), match.id).json()
    assert "coachBehavior" in body and body["coachBehavior"] is None


def test_friendly_team_has_null_coach_behavior(login_as, friendly_match, make_user):
    match, _ = friendly_match
    assert get_team(login_as(make_user(1)), match.id).json()["coachBehavior"] is None


def test_friendly_creator_without_rival_gets_200(login_as, db_session, make_user, make_behaviors):
    make_user(1)
    match = Match(user_1_id=1, name="Esperando", status=MatchStatus.scheduled)
    db_session.add(match)
    db_session.commit()
    add_team(db_session, 1, make_behaviors(1, ["b"], code="pass")[0], match_id=match.id)
    r = get_team(login_as(make_user(1)), match.id)
    assert r.status_code == 200
    assert [m["role"] for m in r.json()["members"]] == ROLE_NAMES


def test_behavior_code_is_never_exposed(login_as, friendly_match, make_user):
    match, _ = friendly_match
    body = get_team(login_as(make_user(1)), match.id).json()
    assert "code" not in str(body)


@pytest.mark.parametrize("status", list(MatchStatus))
def test_no_409_in_any_match_status(login_as, db_session, make_user, make_behaviors, status):
    make_user(1), make_user(2)
    match = Match(
        user_1_id=1,
        user_2_id=2,
        status=status,
        score_1=0 if status == MatchStatus.finished else None,
        score_2=0 if status == MatchStatus.finished else None,
    )
    db_session.add(match)
    db_session.commit()
    add_team(db_session, 1, make_behaviors(1, ["b"], code="pass")[0], match_id=match.id)
    r = get_team(login_as(make_user(1)), match.id)
    assert r.status_code == 200


# --- cambios durante el partido -----------------------------------------------


def test_before_the_match_returns_the_standing_lineup(login_as, db_session, make_user, make_behaviors):
    make_user(1), make_user(2)
    match = Match(user_1_id=1, user_2_id=2, status=MatchStatus.scheduled)
    db_session.add(match)
    db_session.commit()
    team = add_team(db_session, 1, make_behaviors(1, ["b"], code="pass")[0], match_id=match.id)
    add_team(db_session, 2, make_behaviors(2, ["b"], code="pass")[0], match_id=match.id)
    body = get_team(login_as(make_user(1)), match.id).json()
    assert [m["playerId"] for m in body["members"]] == [t.player_id for t in team]


def test_behavior_reassignment_shows_the_new_behavior(login_as, db_session, friendly_match, make_user, make_behaviors):
    match, teams = friendly_match
    new = make_behaviors(1, ["nuevo"], code="pass")[0]
    teams[1][0].behavior_id = new.id  # lo que hace PUT /matches/{id}/behavior
    db_session.commit()
    body = get_team(login_as(make_user(1)), match.id).json()
    assert body["members"][0]["behavior"] == {"id": new.id, "name": "nuevo", "type": "playerBehavior"}


def request_substitution(db, match, team, out_idx=0, in_idx=3):
    user_id = team[out_idx].user_id
    sub = db.get(Substitution, (match.id, user_id, False))
    if sub is None:
        sub = Substitution(
            match_id=match.id,
            user_id=user_id,
            applied=False,
            member_in_id=team[in_idx].id,
            member_out_id=team[out_idx].id,
        )
        db.add(sub)
    else:
        sub.member_in_id = team[in_idx].id
        sub.member_out_id = team[out_idx].id
    db.commit()


def test_pending_substitution_is_not_reflected(login_as, db_session, friendly_match, make_user):
    match, teams = friendly_match
    before = get_team(login_as(make_user(1)), match.id).json()
    request_substitution(db_session, match, teams[1])
    after = get_team(login_as(make_user(1)), match.id).json()
    assert after == before


def test_applied_substitution_swaps_roles(login_as, db_session, friendly_match, make_user):
    match, teams = friendly_match
    team = teams[1]
    request_substitution(db_session, match, team, out_idx=0, in_idx=3)
    SqlAlchemySubstitutionRepository(db_session).apply_by_match(match.id)  # empieza la pausa

    members = {
        m["playerId"]: m["role"]
        for m in get_team(login_as(make_user(1)), match.id).json()["members"]
    }
    assert members[team[3].player_id] == "forward"  # el suplente toma el rol del titular
    assert members[team[0].player_id] == "substitute"  # el titular que sale pasa a substitute


def test_after_the_pause_only_the_last_request_is_reflected(login_as, db_session, friendly_match, make_user):
    match, teams = friendly_match
    team = teams[1]
    request_substitution(db_session, match, team, out_idx=0, in_idx=3)
    request_substitution(db_session, match, team, out_idx=1, in_idx=4)  # reemplaza a la anterior
    SqlAlchemySubstitutionRepository(db_session).apply_by_match(match.id)

    members = {
        m["playerId"]: m["role"]
        for m in get_team(login_as(make_user(1)), match.id).json()["members"]
    }
    assert members[team[0].player_id] == "forward"  # la primera nunca se aplicó
    assert members[team[3].player_id] == "substitute"
    assert members[team[4].player_id] == "midfield"
    assert members[team[1].player_id] == "substitute"


def test_substituted_lineup_keeps_starters_first(login_as, db_session, friendly_match, make_user):
    match, teams = friendly_match
    request_substitution(db_session, match, teams[1], out_idx=2, in_idx=5)
    SqlAlchemySubstitutionRepository(db_session).apply_by_match(match.id)
    body = get_team(login_as(make_user(1)), match.id).json()
    assert [m["role"] for m in body["members"]] == ROLE_NAMES


# --- sin N+1 y solo lectura ---------------------------------------------------


def test_query_count_is_constant_and_read_only(login_as, friendly_match, make_user, count_queries):
    match, _ = friendly_match
    api = login_as(make_user(1))
    with count_queries() as statements:
        assert get_team(api, match.id).status_code == 200
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == len(statements)  # nada de escrituras
    team_queries = [s for s in selects if "team_members" in s]
    assert len(team_queries) == 1  # un solo SELECT para los 6 miembros


def test_does_not_modify_the_match(login_as, db_session, friendly_match, make_user):
    match, _ = friendly_match
    get_team(login_as(make_user(1)), match.id)
    db_session.expire_all()
    assert db_session.get(Match, match.id).status == MatchStatus.started
