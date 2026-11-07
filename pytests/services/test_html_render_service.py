from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.services.html_render_service import HTMLRenderService


@pytest.mark.asyncio
@pytest.mark.parametrize("allow_network,url,allowed", [
    (True, "https://example.com/image.png", True),
    (False, "https://example.com/image.png", False),
    (False, "data:image/png;base64,aW1hZ2U=", True),
])
async def test_registered_network_handler_accepts_route_and_request(allow_network, url, allowed):
    page = SimpleNamespace(set_default_timeout=Mock(), route=AsyncMock(), set_content=AsyncMock())
    request = SimpleNamespace(
        timeout_ms=1000, allow_network=allow_network, html="<p>test</p>", wait_until="load",
        wait_for_selector=None, wait_for_timeout_ms=0,
    )
    await HTMLRenderService()._configure_page(page, request)
    handler = page.route.await_args.args[1]
    route = SimpleNamespace(continue_=AsyncMock(), abort=AsyncMock())

    await handler(route, SimpleNamespace(url=url))

    assert route.continue_.await_count == int(allowed)
    assert route.abort.await_count == int(not allowed)
