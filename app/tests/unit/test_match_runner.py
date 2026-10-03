import asyncio
import json
from contextlib import contextmanager

from app.services.match_broadcast import TickContext, build_tick_payload
from app.services.match_runner import MatchRunner
from app.services.match_setup_service import MatchSetup
from app.simulation.match_rules import Event, Phase, TickResult
from app.simulation.physics import create_initial_state
from app.simulation.state import Team
from app.tests.unit.match_ws_fakes import FakeMatchRepo
from app.tests.unit.simulation_fakes import make_team

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
        self.sockets, self.match_closed = sockets, []

    def subscribers(self, match_id):
        return [(ws, 7) for ws in self.sockets if ws.closed is None]

    async def close_match(self, match_id, code=1000, reason=""):
        self.match_closed.append((match_id, code, reason))


def build(manager, repo, **kwargs):
    setup = MatchSetup(
        make_team(), make_team(first_id=10), 1, countdown_seconds=1,
        club_1_name="Club Uno", club_2_name="Club Dos",
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


def test_a_slow_subscriber_does_not_stop_the_others():
    slow, fast = FakeWs(delay=5), FakeWs()
    run(build(FakeManager([slow, fast]), FakeMatchRepo(), send_timeout=0.05))
    assert len(fast.received) == TOTAL
    assert slow.closed == (1013, "slowClient")


def test_ticks_are_scheduled_every_50ms_without_drift():
    clock, delays = [0.0], []

    async def fake_sleep(delay):
        delays.append(delay)
        clock[0] += delay

    run(build(FakeManager([FakeWs()]), FakeMatchRepo(), sleep=fake_sleep, monotonic=lambda: clock[0]))
    assert len(delays) == TOTAL - 1
    assert all(abs(d - 0.05) < 1e-6 for d in delays)