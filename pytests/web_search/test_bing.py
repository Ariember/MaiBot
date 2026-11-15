"""Bing 搜索请求、真实网址提取与失败语义。"""

import asyncio
import base64

import httpx
import pytest

from src.web_search.adapters.bing import BingSearchAdapter
from src.web_search.adapters.http import MAX_RESPONSE_BYTES
from src.web_search.config import SearchEngineConfig
from src.web_search.models import WebSearchError


@pytest.mark.asyncio
async def test_bing_request_results_redirects_and_limit():
    target = "https://github.com/Mai-with-u/MaiBot"
    encoded = base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "www.bing.com"
        assert request.url.path == "/search"
        assert dict(request.url.params) == {"q": "MaiBot GitHub", "count": "2"}
        assert "Chrome/" in request.headers["User-Agent"]
        return httpx.Response(
            200,
            text=f"""
            <ul id="b_results">
                <li class="b_algo"><h2><a href="https://www.bing.com/search?q=test">导航</a></h2></li>
                <li class="b_algo"><h2><a href="/ck/a?u=a1{encoded}">MaiBot <b>GitHub</b></a></h2>
                    <div class="b_caption"><p>项目 <b>摘要</b></p></div></li>
                <li class="b_algo"><h2><a href="{target}">重复结果</a></h2></li>
                <li class="b_algo"><h2><a href="https://docs.mai-mai.org/">文档</a></h2>
                    <p class="b_lineclamp2">文档摘要</p></li>
                <li class="b_algo"><h2><a href="https://maibot.chat/">官网</a></h2></li>
            </ul>
        """,
        )

    result = await BingSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler)).search("MaiBot GitHub", 2)
    assert result.query == "MaiBot GitHub"
    assert [(hit.title, hit.url, hit.snippet) for hit in result.results] == [
        ("MaiBot GitHub", target, "项目 摘要"),
        ("文档", "https://docs.mai-mai.org/", "文档摘要"),
    ]


@pytest.mark.asyncio
async def test_bing_skips_invalid_links_and_preserves_external_redirect_path():
    html = """
        <li class="b_algo"><h2>无链接</h2></li>
        <li class="b_algo"><h2><a href="/ck/a?u=a1_w">错误编码</a></h2></li>
        <li class="b_algo"><h2><a href="javascript:alert(1)">脚本</a></h2></li>
        <li class="b_algo"><h2><a href="https://example.com/ck/a?u=article">站内地址</a></h2></li>
    """
    adapter = BingSearchAdapter(SearchEngineConfig(), httpx.MockTransport(lambda _: httpx.Response(200, text=html)))
    result = await adapter.search("test", 5)
    assert [(hit.title, hit.url, hit.snippet) for hit in result.results] == [
        ("站内地址", "https://example.com/ck/a?u=article", ""),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,html,message",
    [
        (429, "response-secret", "HTTP 429"),
        (500, "response-secret", "HTTP 500"),
        (200, '<div id="b_captcha">response-secret</div>', "验证码"),
        (200, '<iframe id="b_captchaFrame" src="/captcha/challenge">response-secret</iframe>', "验证码"),
        (200, "<noscript>response-secret</noscript>", "未返回可解析"),
        (200, '<li class="b_algo"><h2>response-secret</h2></li>', "未返回可解析"),
    ],
)
async def test_bing_failure_is_safe_and_not_retried(status, html, message):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, text=html)

    with pytest.raises(WebSearchError, match=message) as exc:
        await BingSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler)).search("test", 5)
    assert "response-secret" not in str(exc.value)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_bing_empty_results_are_success():
    html = '<ul id="b_results"><li class="b_no">There are no results for this search.</li></ul>'
    adapter = BingSearchAdapter(SearchEngineConfig(), httpx.MockTransport(lambda _: httpx.Response(200, text=html)))
    assert (await adapter.search("test", 5)).results == []


@pytest.mark.asyncio
async def test_bing_response_size_is_bounded():
    adapter = BingSearchAdapter(
        SearchEngineConfig(),
        httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1))),
    )
    with pytest.raises(WebSearchError, match="8 MiB"):
        await adapter.search("test", 5)


@pytest.mark.asyncio
@pytest.mark.parametrize("error,message", [(httpx.ReadTimeout, "超时"), (httpx.ConnectError, "ConnectError")])
async def test_bing_network_failure_is_safe(error, message):
    def handler(request: httpx.Request) -> httpx.Response:
        raise error("transport-secret", request=request)

    with pytest.raises(WebSearchError, match=message) as exc:
        await BingSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler)).search("test", 5)
    assert "transport-secret" not in str(exc.value)


@pytest.mark.asyncio
async def test_bing_invalid_proxy_is_safe_before_network():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, text="")

    with pytest.raises(WebSearchError, match="代理") as exc:
        await BingSearchAdapter(
            SearchEngineConfig(proxy="ftp://user:proxy-secret@localhost:7890"),
            httpx.MockTransport(handler),
        ).search("test", 5)
    assert "proxy-secret" not in str(exc.value)
    assert not calls


@pytest.mark.asyncio
async def test_bing_cancellation_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await BingSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler)).search("test", 5)
