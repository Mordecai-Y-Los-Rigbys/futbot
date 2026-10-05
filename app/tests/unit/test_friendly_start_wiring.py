import asyncio
import importlib
import pytest
from unittest.mock import AsyncMock, Mock

from app.api import ws_deps

main_module = importlib.import_module("app.main")

def test_lifespan_recovers_and_shuts_down_friendly_services(monkeypatch):
    expiry = Mock()
    expiry.recover = AsyncMock()

    monkeypatch.setattr(
        main_module, "get_friendly_expiry", lambda: expiry
    )

    async def scenario():
        async with main_module.lifespan(main_module.app):
            expiry.recover.assert_awaited_once_with()
            expiry.shutdown.assert_not_called()

        expiry.shutdown.assert_called_once_with()

    asyncio.run(scenario())