"""搜索引擎与联网提供商的优先级、降级和来源标识。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio

import pytest

from src.core.tooling import ToolExecutionResult, ToolInvocation
from src.plugin_runtime.capabilities import web
from src.web_search.adapters.bing import BingSearchAdapter
from src.web_search.adapters.google import GoogleSearchAdapter
from src.web_search.config import SearchEngineConfig, WebConfig, WebSearchTaskConfig, resolve_web_search_config
from src.web_search.models import SearchHit, SearchResult, WebSearchError
from src.web_search.provider import WebSearchToolProvider
from src.web_search.service import WebSearchService


def settings(priority="provider_first", provider=True, enabled=True, engine="google"):
    return resolve_web_search_config(
        WebConfig(services={"step": {"adapter": "stepsearch_mcp", "server_ref": "stepsearch"}}),
        WebSearchTaskConfig(model_list=["step"] if provider else []),
        SearchEngineConfig(enabled=enabled, priority=priority, engine=engine),
    )


@pytest.fixture
def search(monkeypatch):
    engine = AsyncMock(return_value=SearchResult("query", [SearchHit("Google", "https://example.com", "摘要")]))
    monkeypatch.setattr(GoogleSearchAdapter, "search", engine)
    bing = AsyncMock(return_value=SearchResult("query", [SearchHit("Bing", "https://example.com", "摘要")]))
    monkeypatch.setattr(BingSearchAdapter, "search", bing)
    mcp = SimpleNamespace(
        call_tool_invocation=AsyncMock(
            return_value=ToolExecutionResult(
                tool_name="web_search",
                success=True,
                structured_content={
                    "results": [{"title": "Provider", "url": "https://example.com", "snippet": "摘要"}]
                },
            )
        )
    )
    return WebSearchService(mcp), mcp.call_tool_invocation, engine, bing


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "priority,preferred,failed,source,calls",
    [
        ("provider_first", "google", [], "step", (1, 0, 0)),
        ("provider_first", "google", ["provider"], "search_engine:google", (1, 1, 0)),
        ("provider_first", "google", ["provider", "google"], "search_engine:bing", (1, 1, 1)),
        ("provider_first", "bing", ["provider"], "search_engine:bing", (1, 0, 1)),
        ("engine_first", "google", [], "search_engine:google", (0, 1, 0)),
        ("engine_first", "google", ["google"], "search_engine:bing", (0, 1, 1)),
        ("engine_first", "google", ["google", "bing"], "step", (1, 1, 1)),
        ("engine_first", "bing", [], "search_engine:bing", (0, 0, 1)),
        ("engine_first", "bing", ["bing"], "search_engine:google", (0, 1, 1)),
        ("engine_first", "bing", ["bing", "google"], "step", (1, 1, 1)),
    ],
)
async def test_search_priority_and_fallback(search, priority, preferred, failed, source, calls):
    service, provider, engine, bing = search
    if "provider" in failed:
        provider.return_value = ToolExecutionResult(tool_name="web_search", success=False)
    if "google" in failed:
        engine.side_effect = WebSearchError("Google 请求超时")
    if "bing" in failed:
        bing.side_effect = WebSearchError("Bing 请求超时")
    result = await service.execute(
        settings(priority, engine=preferred), ToolInvocation(tool_name="web_search", arguments={"query": "query"})
    )
    assert result.service == source
    assert (provider.await_count, engine.await_count, bing.await_count) == calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "preferred,google_fails,source",
    [
        ("google", False, "search_engine:google"),
        ("google", True, "search_engine:bing"),
        ("bing", False, "search_engine:bing"),
    ],
)
async def test_unassigned_provider_uses_engine_and_preserves_actual_source(
    search, monkeypatch, preferred, google_fails, source
):
    service, provider, engine, bing = search
    config = settings(provider=False, engine=preferred)
    if google_fails:
        engine.side_effect = WebSearchError("Google 要求验证码")
    tools = WebSearchToolProvider(service, lambda: config)
    assert [tool.name for tool in await tools.list_tools()] == ["web_search"]
    invocation = ToolInvocation(tool_name="web_search", arguments={"query": "query"}, session_id="chat")
    result = await tools.invoke(invocation)
    assert result.success
    assert result.metadata["service"] == source
    assert result.structured_content["service"] == source
    monkeypatch.setattr(web, "get_config", lambda: config)
    monkeypatch.setattr(web, "get_service", lambda: service)
    plugin_result = await web.call("test", "web.search", {"query": "query"})
    assert plugin_result["result"]["service"] == source
    provider.assert_not_awaited()
    assert (engine.await_count, bing.await_count) == (
        2 if preferred == "google" else 0,
        2 if source.endswith("bing") else 0,
    )


@pytest.mark.asyncio
async def test_search_switch_keeps_assigned_fetch(search):
    service, provider, engine, bing = search
    config = settings(enabled=False)
    tools = WebSearchToolProvider(service, lambda: config)
    assert [tool.name for tool in await tools.list_tools()] == ["web_fetch"]
    with pytest.raises(WebSearchError, match="未配置"):
        await service.execute(config, ToolInvocation(tool_name="web_search", arguments={"query": "query"}))
    provider.assert_not_awaited()
    engine.assert_not_awaited()
    bing.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {"query": " "},
        {"query": "query", "max_results": True},
        {"query": "query", "service": "override"},
    ],
)
async def test_invalid_arguments_do_not_trigger_fallback(search, arguments):
    service, provider, engine, bing = search
    with pytest.raises(WebSearchError):
        await service.execute(settings(), ToolInvocation(tool_name="web_search", arguments=arguments))
    provider.assert_not_awaited()
    engine.assert_not_awaited()
    bing.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_provider_search_is_success_without_fallback(search):
    service, provider, engine, bing = search
    provider.return_value.structured_content = {"results": []}
    result = await service.execute(settings(), ToolInvocation(tool_name="web_search", arguments={"query": "query"}))
    assert result.results == []
    assert result.service == "step"
    engine.assert_not_awaited()
    bing.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_propagates_without_fallback(search):
    service, provider, engine, bing = search
    provider.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await service.execute(settings(), ToolInvocation(tool_name="web_search", arguments={"query": "query"}))
    engine.assert_not_awaited()
    bing.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_can_handle_query_beyond_provider_limit(search):
    service, provider, engine, bing = search
    config = settings()
    config.services["step"].adapter = "deepseek"
    config.services["step"].api_key = "test-key"
    tools = WebSearchToolProvider(service, lambda: config)
    spec = (await tools.list_tools())[0]
    assert spec.parameters_schema["properties"]["query"]["maxLength"] == 1000
    query = "a" * 129
    result = await service.execute(config, ToolInvocation(tool_name="web_search", arguments={"query": query}))
    assert result.service == "search_engine:google"
    engine.assert_awaited_once_with(query, 5)
    provider.assert_not_awaited()
    bing.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_engine_result_does_not_fall_through(search):
    service, provider, engine, bing = search
    engine.return_value.results = []
    result = await service.execute(
        settings("engine_first"), ToolInvocation(tool_name="web_search", arguments={"query": "query"})
    )
    assert result.results == [] and result.service == "search_engine:google"
    provider.assert_not_awaited()
    bing.assert_not_awaited()


@pytest.mark.asyncio
async def test_all_failed_sources_are_reported(search):
    service, provider, engine, bing = search
    provider.return_value = ToolExecutionResult(tool_name="web_search", success=False)
    engine.side_effect = WebSearchError("Google 要求验证码")
    bing.side_effect = WebSearchError("Bing 请求超时")
    with pytest.raises(WebSearchError) as exc:
        await service.execute(settings(), ToolInvocation(tool_name="web_search", arguments={"query": "query"}))
    assert all(name in str(exc.value) for name in ("step", "search_engine:google", "search_engine:bing"))
