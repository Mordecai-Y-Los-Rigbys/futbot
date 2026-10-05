import asyncio
import importlib
from unittest.mock import AsyncMock, Mock

from app.api import ws_deps
from app.services.match_runner import MatchRunner

main_module = importlib.import_module("app.main")


def test_starting_a_friendly_starts_it_on_the_shared_runner(monkeypatch):
    runner = ws_deps.get_match_runner()
    started = []
    monkeypatch.setattr(runner, "start", started.append)

    asyncio.run(ws_deps.get_friendly_start()._on_start(42))

    assert started == [42]


def test_lifespan_recovers_and_shuts_down_friendly_services(monkeypatch):
    expiry = Mock()
    expiry.recover = AsyncMock()

    start = Mock()
    start.recover = AsyncMock()

    runner = Mock()
    runner.shutdown = AsyncMock()

    assert callable(
        getattr(main_module, "get_friendly_start", None)
    ), "main.py debe importar get_friendly_start"
    assert callable(
        getattr(main_module, "get_match_runner", None)
    ), "main.py debe importar get_match_runner"

    monkeypatch.setattr(main_module, "get_friendly_expiry", lambda: expiry)
    monkeypatch.setattr(main_module, "get_friendly_start", lambda: start)
    monkeypatch.setattr(main_module, "get_match_runner", lambda: runner)

    async def scenario():
        async with main_module.lifespan(main_module.app):
            expiry.recover.assert_awaited_once_with()
            expiry.shutdown.assert_not_called()
            start.shutdown.assert_not_called()
            runner.shutdown.assert_not_awaited()

        expiry.shutdown.assert_called_once_with()
        runner.shutdown.assert_awaited_once_with()

    asyncio.run(scenario())


def test_ws_deps_creates_a_real_match_runner():
    assert isinstance(ws_deps.get_match_runner(), MatchRunner)
