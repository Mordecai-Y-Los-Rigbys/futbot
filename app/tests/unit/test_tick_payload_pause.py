from app.services.match_broadcast import TickContext, build_tick_payload
from app.simulation.match_rules import Event, PauseReason, Phase, TickResult
from app.simulation.physics import create_initial_state
from app.simulation.run import default_team as make_team
from app.tests.unit.tick_schema import TickPayload

CTX = TickContext(club_1="Club Uno", club_2="Club Dos", countdown_seconds=5)


def result(phase=Phase.PAUSED, event=None, **kw) -> TickResult:
    state = create_initial_state(make_team().players, make_team(first_id=10).players, 1)
    return TickResult(3, phase, event, state, 1, 0, 45.0, 135.0, 1, **kw)


def pause_kw(remaining, reason=PauseReason.HYDRATION):
    return dict(pause_reason=reason, pause_remaining_seconds=remaining, pause_duration_seconds=15)


def test_first_pause_tick_has_event_and_remaining():
    p = build_tick_payload(result(event=Event.PAUSE, **pause_kw(15)), CTX)
    assert p["phase"] == "paused"
    assert p["event"] == {"type": "pause", "reason": "hydration", "durationSeconds": 15}
    assert p["pauseRemainingSeconds"] == 15
    assert p["elapsedTime"] == 45
    TickPayload.model_validate(p)


def test_following_pause_ticks_have_no_event_but_the_remaining_time():
    p = build_tick_payload(result(**pause_kw(7)), CTX)
    assert p["event"] is None and p["pauseRemainingSeconds"] == 7
    TickPayload.model_validate(p)


def test_last_pause_tick_has_one_remaining():
    p = build_tick_payload(result(**pause_kw(1)), CTX)
    assert p["pauseRemainingSeconds"] == 1


def test_halftime_reason():
    p = build_tick_payload(
        result(event=Event.PAUSE, **pause_kw(15, PauseReason.HALFTIME)), CTX
    )
    assert p["event"]["reason"] == "halftime"
    TickPayload.model_validate(p)


def test_non_pause_ticks_have_null_pause_remaining_seconds():
    for phase in (Phase.COUNTDOWN, Phase.PLAYING):
        assert build_tick_payload(result(phase=phase), CTX)["pauseRemainingSeconds"] is None


def test_the_key_is_always_present():
    for phase in (Phase.COUNTDOWN, Phase.PLAYING, Phase.PAUSED):
        kw = pause_kw(3) if phase is Phase.PAUSED else {}
        assert "pauseRemainingSeconds" in build_tick_payload(result(phase=phase, **kw), CTX)


def test_penalty_scores_are_zero_and_matchend_has_null_penalties():
    p = build_tick_payload(result(phase=Phase.PLAYING), CTX)
    assert (p["penaltyScore1"], p["penaltyScore2"]) == (0, 0)
    end = build_tick_payload(result(phase=Phase.FINISHED, event=Event.MATCH_END), CTX)
    assert end["event"]["result"]["penalties"] is None
    TickPayload.model_validate(end)