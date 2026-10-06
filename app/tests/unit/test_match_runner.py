import asyncio
import json
from contextlib import contextmanager

from app.services.match_broadcast import TickContext, build_tick_payload, _closing
from app.services.match_runner import MatchRunner
from app.services.match_setup_service import MatchSetup
from app.simulation.match_rules import Event, Phase, TickResult
from app.simulation.physics import create_initial_state
from app.simulation.state import Team
from app.tests.unit.match_ws_fakes import FakeMatchRepo
from app.simulation.run import default_team as make_team
import logging

TOTAL = 40  # 1 s de cuenta regresiva (20 ticks) + 1 s de juego (20 ticks)
CTX = TickContext(club_1="Club Uno", club_2="Club Dos", countdown_seconds=1)
TICK_KEYS = {"type", "players", "ballPosition", "score1", "score2", "elapsedTime", "phase", "event"}


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


def build(manager, repo, **kwargs):
    setup = MatchSetup(
        make_team(),
        make_team(first_id=10),
        1,
        countdown_seconds=1,
        club_1_name="Club Uno",
        club_2_name="Club Dos",
    )

    @contextmanager
    def scope():
        yield repo

    async def no_sleep(_):
        pass

    kwargs.setdefault("sleep", no_sleep)
    return MatchRunner(manager, lambda _id: setup, scope, seed_factory=lambda: 42, **kwargs)


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
        "result": {"score1": repo.results[1][0], "score2": repo.results[1][1]},
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
