import asyncio
import itertools
import json
import logging
from contextlib import contextmanager

from app.services.match_broadcast import TickContext, build_tick_payload, _closing
from app.services.match_runner import MatchRunner
from app.services.match_setup_service import MatchSetup
from app.simulation.match_rules import Event, Phase, TickResult
from app.simulation.physics import create_initial_state
from app.simulation.state import Team
from app.tests.unit.match_ws_fakes import FakeMatchRepo, FakeSubstitutionRepo
from app.tests.unit.tick_schema import TickPayload
from app.simulation.run import default_team as make_team

TOTAL = 40  # 1 s de cuenta regresiva (20 ticks) + 1 s de juego (20 ticks), un solo período
CTX = TickContext(club_1="Club Uno", club_2="Club Dos", countdown_seconds=1)
TICK_KEYS = {
    "type",
    "players",
    "ballPosition",
    "score1",
    "score2",
    "penaltyScore1",
    "penaltyScore2",
    "elapsedTime",
    "pauseRemainingSeconds",
    "phase",
    "event",
}

# 4 períodos, 2 s de juego (10 ticks por período), cuentas de 1 s y pausas de 1 s (20 ticks).
PAUSED = dict(periods=4, pause_seconds=1, duration=2)
PAUSED_TOTAL = 20 + 40 + 3 * (20 + 20)  # cuenta + 2 s de juego + 3 × (pausa + cuenta)
# Igual, pero con pausas de 2 s (40 ticks): permite entrar "a la mitad" con remaining < duración.
LATE = dict(periods=4, pause_seconds=2, duration=2)


class FakeWs:
    def __init__(self, delay: float = 0.0, probe=None):
        self.delay, self.probe, self.received, self.closed = delay, probe, [], None

    async def send_text(self, text):
        if self.delay:
            await asyncio.sleep(self.delay)
        self.received.append(json.loads(text))
        if self.probe:
            self.probe(self.received[-1])

    async def close(self, code=1000, reason=None):
        self.closed = (code, reason)


class FakeManager:
    def __init__(self, sockets):
        self.sockets, self.match_closed, self.evicted = sockets, [], []

    def subscribers(self, match_id):
        gone = {ws for _, _, ws in self.evicted}
        return [(ws, 7) for ws in self.sockets if ws.closed is None and ws not in gone]

    def evict(self, match_id, user_id, websocket):
        self.evicted.append((match_id, user_id, websocket))

    async def close_match(self, match_id, code=1000, reason=""):
        self.match_closed.append((match_id, code, reason))


def build(manager, repo, substitutions=None, periods=1, pause_seconds=15, duration=1, **kwargs):
    substitutions = substitutions if substitutions is not None else FakeSubstitutionRepo()
    setup = MatchSetup(
        make_team(),
        make_team(first_id=10),
        duration,
        countdown_seconds=1,
        club_1_name="Club Uno",
        club_2_name="Club Dos",
        periods=periods,
        pause_seconds=pause_seconds,
    )

    @contextmanager
    def scope():
        yield repo

    @contextmanager
    def substitution_scope():
        yield substitutions

    async def no_sleep(_):
        pass

    kwargs.setdefault("sleep", no_sleep)
    return MatchRunner(
        manager,
        lambda _id: setup,
        scope,
        substitution_scope,
        seed_factory=lambda: 42,
        **kwargs,
    )


def run(runner):
    async def main():
        await runner.start(1)
        # El close del suscriptor lento es una tarea aparte: se espera acá.
        await asyncio.gather(*list(_closing))

    asyncio.run(main())


def test_subscriber_gets_every_tick_in_order_and_the_match_ends():
    ws = FakeWs()
    manager = FakeManager([ws])
    repo = FakeMatchRepo()
    run(build(manager, repo))

    ticks = ws.received
    assert len(ticks) == TOTAL
    assert [t["phase"] for t in ticks[:20]] == ["countdown"] * 20
    assert ticks[0]["event"] == {"type": "periodStart", "periodNumber": 1, "countdownSeconds": 1}
    assert all(t["event"] is None for t in ticks[1:20])
    assert ticks[20]["phase"] == "playing"
    last = ticks[-1]
    assert last["phase"] == "finished"
    assert last["event"] == {
        "type": "matchEnd",
        "result": {
            "score1": repo.results[1][0],
            "score2": repo.results[1][1],
            "penalties": None,
        },
    }
    assert manager.match_closed == [(1, 1000, "matchEnd")]


def test_match_stays_scheduled_during_countdown_then_started_then_finished():
    repo = FakeMatchRepo()
    repo.add(1)  # scheduled
    seen = []
    ws = FakeWs(probe=lambda tick: seen.append((tick["phase"], repo.states[1].status)))
    run(build(FakeManager([ws]), repo))

    assert all(status == "scheduled" for phase, status in seen if phase == "countdown")
    assert all(status == "started" for phase, status in seen if phase == "playing")
    assert repo.history == ["started", "finished"]
    assert repo.states[1].status == "finished"


def test_payload_matches_the_asyncapi_and_has_no_behaviors():
    ws = FakeWs()
    run(build(FakeManager([ws]), FakeMatchRepo()))
    for tick in ws.received:
        assert set(tick) == TICK_KEYS and tick["type"] == "tick"
        assert isinstance(tick["elapsedTime"], int)
        assert (tick["penaltyScore1"], tick["penaltyScore2"]) == (0, 0)
        assert tick["pauseRemainingSeconds"] is None  # sin pausas con un solo período
        text = json.dumps(tick).lower()
        assert "behavior" not in text and "code" not in text
        assert len(tick["players"]) == 6
        assert all(set(p) == {"playerId", "position"} for p in tick["players"])
        points = [tick["ballPosition"]] + [p["position"] for p in tick["players"]]
        assert all(round(v, 2) == v for pt in points for v in (pt["x"], pt["y"]))


def test_goal_event_names_the_scoring_club():
    team_1, team_2 = make_team(), make_team(first_id=10)
    state = create_initial_state(team_1.players, team_2.players, 1)
    result = TickResult(5, Phase.PLAYING, Event.GOAL, state, 0, 1, 0.25, 0.75, 1, Team.AWAY)
    payload = build_tick_payload(result, CTX)
    assert payload["event"] == {"type": "goal", "scoringClub": "Club Dos"}
    assert (payload["score1"], payload["score2"]) == (0, 1)


def test_a_slow_subscriber_is_evicted_once_and_does_not_stop_the_others():
    slow, fast = FakeWs(delay=5), FakeWs()
    manager = FakeManager([slow, fast])
    run(build(manager, FakeMatchRepo(), send_timeout=0.05))

    assert len(fast.received) == TOTAL
    assert slow.closed == (1013, "slowClient")
    assert manager.evicted == [(1, 7, slow)]  # una sola vez, no en cada tick


def test_ticks_are_scheduled_every_50ms_without_drift():
    clock, delays = [0.0], []

    async def fake_sleep(delay):
        delays.append(delay)
        clock[0] += delay

    run(
        build(
            FakeManager([FakeWs()]), FakeMatchRepo(), sleep=fake_sleep, monotonic=lambda: clock[0]
        )
    )
    assert len(delays) == TOTAL - 1
    assert all(abs(d - 0.05) < 1e-6 for d in delays)


def test_seed_is_saved_and_logged_before_the_first_tick(caplog):
    ws = FakeWs()
    repo = FakeMatchRepo()
    seen = []
    ws.probe = lambda tick: seen.append(dict(repo.seeds)) if not seen else None

    with caplog.at_level(logging.INFO):
        run(build(FakeManager([ws]), repo))

    assert repo.seeds == {1: 42}  # seed_factory=lambda: 42
    assert seen[0] == {1: 42}  # ya estaba guardada en el primer tick
    assert "seed=42" in caplog.text


def test_if_saving_the_seed_fails_the_match_is_still_played(caplog):
    ws = FakeWs()
    repo = FakeMatchRepo()

    def boom(match_id, seed):
        raise RuntimeError("base caída")

    repo.save_seed = boom
    with caplog.at_level(logging.INFO):
        run(build(FakeManager([ws]), repo))

    assert len(ws.received) == TOTAL  # el partido se jugó completo
    assert "No se pudo guardar la seed" in caplog.text
    assert "seed=42" in caplog.text  # igual quedó en el log


# --- pausas -------------------------------------------------------------------


def test_pause_ticks_follow_the_contract_and_only_they_carry_the_remaining_time():
    ws = FakeWs()
    run(build(FakeManager([ws]), FakeMatchRepo(), **PAUSED))
    assert len(ws.received) == PAUSED_TOTAL
    for tick in ws.received:
        TickPayload.model_validate(tick)
        assert (tick["pauseRemainingSeconds"] is not None) == (tick["phase"] == "paused")
    first = next(t for t in ws.received if t["phase"] == "paused")
    assert first["event"] == {"type": "pause", "reason": "hydration", "durationSeconds": 1}
    assert first["pauseRemainingSeconds"] == 1
    reasons = [
        t["event"]["reason"]
        for t in ws.received
        if t["event"] and t["event"]["type"] == "pause"
    ]
    assert reasons == ["hydration", "halftime", "hydration"]


def test_the_clock_does_not_advance_during_pauses_and_countdowns():
    ws = FakeWs()
    run(build(FakeManager([ws]), FakeMatchRepo(), **PAUSED))
    frozen = [t["elapsedTime"] for t in ws.received if t["phase"] in ("paused", "countdown")]
    assert frozen and all(isinstance(v, int) for v in frozen)
    assert ws.received[-1]["elapsedTime"] == 2  # 2 s de juego, sin contar las pausas


def test_substitutions_are_consumed_when_each_pause_ends_before_the_next_countdown():
    repo = FakeMatchRepo()
    substitutions = FakeSubstitutionRepo()
    seen = []
    ws = FakeWs(
        probe=lambda t: (
            seen.append((t["event"]["periodNumber"], len(substitutions.pause_ends)))
            if t["event"] and t["event"]["type"] == "periodStart"
            else None
        )
    )
    run(build(FakeManager([ws]), repo, substitutions, **PAUSED))
    assert substitutions.pause_ends == [1, 1, 1]
    assert seen == [(1, 0), (2, 1), (3, 2), (4, 3)]


def test_failure_deleting_substitutions_does_not_stop_the_match(caplog):
    repo = FakeMatchRepo()
    substitutions = FakeSubstitutionRepo()

    def boom(match_id):
        raise RuntimeError("base caída")

    substitutions.delete_first_per_team = boom
    ws = FakeWs()
    run(build(FakeManager([ws]), repo, substitutions, **PAUSED))
    assert len(ws.received) == PAUSED_TOTAL
    assert ws.received[-1]["phase"] == "finished"
    assert "No se pudieron borrar los cambios" in caplog.text


def test_late_subscriber_gets_the_current_pause_then_the_restarted_countdown_then_play():
    early, late = FakeWs(), FakeWs()
    manager = FakeManager([early])
    count = {"paused": 0}

    def join_mid_pause(tick):
        if tick["phase"] == "paused":
            count["paused"] += 1
            if count["paused"] == 25 and late not in manager.sockets:
                manager.sockets.append(late)

    early.probe = join_mid_pause
    run(build(manager, FakeMatchRepo(), **LATE))

    first = late.received[0]
    assert first["phase"] == "paused" and first["event"] is None
    assert first["pauseRemainingSeconds"] < 2  # menor a la duración: entró a la mitad
    assert late.received == early.received[-len(late.received) :]  # sin replay

    head = late.received[:15]  # lo que queda de la primera pausa
    assert [t["phase"] for t in head] == ["paused"] * 15
    assert [t["pauseRemainingSeconds"] for t in head] == [1] * 14 + [0]

    phases = [k for k, _ in itertools.groupby(t["phase"] for t in late.received)]
    assert phases[:3] == ["paused", "countdown", "playing"]

    initial = early.received[0]  # tick 0: posiciones iniciales
    countdown = [t for t in late.received if t["phase"] == "countdown"][:20]
    assert len(countdown) == 20
    assert all(t["players"] == initial["players"] for t in countdown)
    assert all(t["ballPosition"] == initial["ballPosition"] for t in countdown)


def test_reconnecting_client_is_a_new_subscriber_and_sees_the_same_pause_stream():
    first, second = FakeWs(), FakeWs()
    manager = FakeManager([first])
    count = {"n": 0}

    def reconnect(tick):
        if tick["phase"] == "paused":
            count["n"] += 1
            if count["n"] == 3:
                manager.sockets.remove(first)  # se cae
                manager.sockets.append(second)  # reconecta con el mismo token

    first.probe = reconnect
    run(build(manager, FakeMatchRepo(), **PAUSED))
    assert second.received[0]["phase"] == "paused"
    assert second.received[0]["pauseRemainingSeconds"] is not None
    assert second.received[-1]["phase"] == "finished"
    assert any(t["phase"] == "countdown" for t in second.received)
    for tick in second.received:
        TickPayload.model_validate(tick)