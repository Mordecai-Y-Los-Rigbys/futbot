from datetime import datetime, timezone

import pytest

from app.domain.match import MatchStatus
from app.models.league import LeagueStatus
from app.models.match import Match


@pytest.fixture()
def make_match(db_session):
    def _make(league, club1, club2, score=(0, 0), penalties=None, status=MatchStatus.finished):
        finished = status == MatchStatus.finished
        p1, p2, winner = penalties or (None, None, None)
        match = Match(
            league_id=league.id,
            user_1_id=club1.id,
            user_2_id=club2.id,
            status=status,
            score_1=score[0] if finished else None,
            score_2=score[1] if finished else None,
            penalty_score_1=p1,
            penalty_score_2=p2,
            penalty_winner=winner,
            scheduled_at=datetime.now(timezone.utc),
        )
        db_session.add(match)
        db_session.commit()
        return match

    return _make


@pytest.fixture()
def league_of_three(create_user, make_league, add_participant):
    """Liga pública iniciada con tres participantes: a (creador), b y c."""
    a, b, c = create_user("a"), create_user("b"), create_user("c")
    league = make_league(a, status="started")
    add_participant(league, b)
    add_participant(league, c)
    return league, a, b, c


@pytest.fixture()
def private_league(create_user, make_league, add_participant):
    creator, member = create_user("creator"), create_user("member")
    league = make_league(creator, status="started", private=True)
    add_participant(league, member)
    return league, creator, member


def by_name(body):
    return {e["name"]: e for e in body}


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"code", "message"}
    assert body["code"] == code


# --- 401 / 404 / 409 -----------------------------------------------------------


def test_no_cookie_is_401(client, league_of_three):
    league, *_ = league_of_three
    assert_error(client.get(f"/leagues/{league.id}/ranking"), 401, None)


def test_401_beats_404(client):
    assert_error(client.get("/leagues/abc/ranking"), 401, None)


@pytest.mark.parametrize("league_id", ["999999", "abc", "0", "-1", "1.5", "2147483648"])
def test_invalid_or_missing_league_is_404(create_user, login_as, league_id):
    api = login_as(create_user("u"))
    assert_error(api.get(f"/leagues/{league_id}/ranking"), 404, None)


def test_404_beats_403(create_user, make_league, login_as):
    make_league(create_user("creator"), status="started", private=True)
    api = login_as(create_user("outsider"))
    assert_error(api.get("/leagues/999999/ranking"), 404, None)


@pytest.mark.parametrize(
    "status, code", [("preparation", "leagueNotStarted"), ("cancelled", "leagueCancelled")]
)
def test_league_without_ranking_is_409(create_user, make_league, login_as, status, code):
    creator = create_user("a")
    league = make_league(creator, status=status)
    assert_error(login_as(creator).get(f"/leagues/{league.id}/ranking"), 409, code)


def test_finished_league_is_200(create_user, make_league, login_as):
    creator = create_user("a")
    league = make_league(creator, status="finished")
    assert login_as(creator).get(f"/leagues/{league.id}/ranking").status_code == 200


# --- contenido -----------------------------------------------------------------


def test_just_started_lists_everyone_at_zero(login_as, league_of_three):
    league, a, *_ = league_of_three
    r = login_as(a).get(f"/leagues/{league.id}/ranking")
    assert r.status_code == 200
    body = r.json()
    assert [e["name"] for e in body] == ["club-a", "club-b", "club-c"]
    assert set(body[0]) == {
        "position", "name", "avatar", "played", "wonRegular", "wonPenalties",
        "drawn", "lost", "goals", "goalDifference", "score",
    }
    for e in body:
        assert e["position"] == 1
        assert all(e[k] == 0 for k in set(e) - {"position", "name", "avatar"})


def test_entry_has_club_avatar(db_session, login_as, league_of_three):
    league, a, b, _ = league_of_three
    b.avatar = 4
    db_session.commit()
    body = by_name(login_as(a).get(f"/leagues/{league.id}/ranking").json())
    assert body["club-b"]["avatar"] == 4


def test_regular_win_and_draw(login_as, make_match, league_of_three):
    league, a, b, c = league_of_three
    make_match(league, a, b, score=(3, 1))
    make_match(league, b, c, score=(2, 2))
    body = by_name(login_as(a).get(f"/leagues/{league.id}/ranking").json())
    assert (body["club-a"]["score"], body["club-a"]["wonRegular"], body["club-a"]["goalDifference"]) == (3, 1, 2)
    assert (body["club-b"]["score"], body["club-b"]["drawn"], body["club-b"]["lost"], body["club-b"]["played"]) == (1, 1, 1, 2)
    assert (body["club-c"]["score"], body["club-c"]["drawn"], body["club-c"]["goals"]) == (1, 1, 2)


def test_penalties_win_counts_2_and_loss_counts_0(login_as, make_match, league_of_three):
    league, a, b, _ = league_of_three
    make_match(league, a, b, score=(1, 1), penalties=(3, 4, 2))
    body = by_name(login_as(a).get(f"/leagues/{league.id}/ranking").json())
    b_entry, a_entry = body["club-b"], body["club-a"]
    assert (b_entry["score"], b_entry["wonPenalties"], b_entry["wonRegular"], b_entry["drawn"]) == (2, 1, 0, 0)
    assert (a_entry["score"], a_entry["lost"], a_entry["drawn"]) == (0, 1, 0)
    assert a_entry["goals"] == b_entry["goals"] == 1  # la tanda no suma
    assert a_entry["goalDifference"] == b_entry["goalDifference"] == 0


def test_only_finished_matches_of_this_league_count(
    make_league, add_participant, login_as, make_match, league_of_three
):
    league, a, b, c = league_of_three
    other = make_league(c, name="Otra", status="started")
    add_participant(other, a)
    make_match(other, a, c, score=(5, 0))
    make_match(league, a, b, status=MatchStatus.started)
    make_match(league, b, c, status=MatchStatus.scheduled)
    body = login_as(a).get(f"/leagues/{league.id}/ranking").json()
    assert all(e["played"] == 0 and e["goals"] == 0 for e in body)


def test_order_and_shared_position(login_as, make_match, league_of_three):
    league, a, b, c = league_of_three
    make_match(league, a, b, score=(1, 1))
    make_match(league, a, c, score=(1, 1))
    make_match(league, b, c, score=(0, 0))
    body = login_as(a).get(f"/leagues/{league.id}/ranking").json()
    # a: 2 pts, 2 goles; b y c: 2 pts, 1 gol, empatados en todo
    assert [(e["name"], e["position"]) for e in body] == [("club-a", 1), ("club-b", 2), ("club-c", 2)]


# --- acceso --------------------------------------------------------------------


def test_outsider_without_access_is_403(create_user, login_as, private_league):
    league, *_ = private_league
    r = login_as(create_user("outsider")).get(f"/leagues/{league.id}/ranking")
    assert_error(r, 403, "leagueAccessRequired")


def test_creator_and_participant_have_access(login_as, private_league):
    league, creator, member = private_league
    assert login_as(creator).get(f"/leagues/{league.id}/ranking").status_code == 200
    assert login_as(member).get(f"/leagues/{league.id}/ranking").status_code == 200


def test_unlocked_session_has_access_but_other_session_does_not(create_user, login_as, private_league):
    league, *_ = private_league
    outsider = create_user("outsider")
    unlocked, other = login_as(outsider), login_as(outsider)
    assert unlocked.post(f"/leagues/{league.id}/access", json={"password": "secret"}).status_code == 204
    assert unlocked.get(f"/leagues/{league.id}/ranking").status_code == 200
    assert_error(other.get(f"/leagues/{league.id}/ranking"), 403, "leagueAccessRequired")


def test_public_league_is_open_to_any_user(create_user, login_as, league_of_three):
    league, *_ = league_of_three
    assert login_as(create_user("outsider")).get(f"/leagues/{league.id}/ranking").status_code == 200


def test_leaver_keeps_access_in_unlocked_session(
    db_session, create_user, make_league, add_participant, login_as
):
    creator, member = create_user("creator"), create_user("member")
    league = make_league(creator, private=True)  # en preparation para poder abandonar
    add_participant(league, member)
    api = login_as(member)
    assert api.post(f"/leagues/{league.id}/access", json={}).status_code == 204
    assert api.delete(f"/leagues/{league.id}/participants/me").status_code == 204
    league.status = LeagueStatus.started
    db_session.commit()
    assert api.get(f"/leagues/{league.id}/ranking").status_code == 200


def test_403_beats_409(create_user, make_league, login_as):
    league = make_league(create_user("creator"), private=True)  # en preparation
    r = login_as(create_user("outsider")).get(f"/leagues/{league.id}/ranking")
    assert_error(r, 403, "leagueAccessRequired")