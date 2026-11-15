"""Google 搜索请求、页面解析与失败语义。"""

import asyncio

import httpx
import pytest

from src.web_search.adapters.google import GoogleSearchAdapter
from src.web_search.config import SearchEngineConfig
from src.web_search.models import WebSearchError


@pytest.mark.asyncio
async def test_google_request_and_opera_desktop_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "www.google.com.hk"
        assert request.url.path == "/search"
        assert dict(request.url.params) == {
            "q": "麦麦 搜索",
            "hl": "zh-CN",
            "client": "ms-opera-mini",
            "ie": "utf8",
            "filter": "0",
        }
        assert "Opera Mini" in request.headers["User-Agent"]
        assert "zh-CN" in request.headers["Accept-Language"]
        assert "CONSENT=YES+" in request.headers["Cookie"]
        return httpx.Response(
            200,
            text="""
            <div class="Gx5Zad"><div><a href="/url?q=https%3A%2F%2Fexample.com%2Fopera">
                <div><h3>Opera <b>标题</b></h3></div></a></div>
                <div><div class="ilUpNd H66NU">Opera <b>摘要</b></div></div></div>
            <div><div><a href="https://example.com/desktop"><h3>桌面标题</h3></a></div>
                <div class="VwiC3b">桌面摘要</div></div>
        """,
        )

    result = await GoogleSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler)).search("麦麦 搜索", 5)
    assert result.query == "麦麦 搜索"
    assert [(hit.title, hit.url, hit.snippet) for hit in result.results] == [
        ("Opera 标题", "https://example.com/opera", "Opera 摘要"),
        ("桌面标题", "https://example.com/desktop", "桌面摘要"),
    ]


@pytest.mark.asyncio
async def test_google_unwraps_links_filters_navigation_and_limits_unique_results():
    html = """
        <a href="https://www.google.com/search?q=test"><h3>导航</h3></a>
        <a href="https://maps.google.com/place"><h3>地图</h3></a>
        <a href="/search?q=test"><h3>相对导航</h3></a>
        <a href="javascript:alert(1)"><h3>脚本</h3></a>
        <h3>没有链接</h3>
        <a href="https://www.google.com.hk/url?url=https%3A%2F%2Fexample.com%2Fa"><h3>A</h3></a>
        <a href="https://example.com/a"><h3>重复 A</h3></a>
        <a href="/url?q=https%3A%2F%2Fexample.com%2Fb&amp;sa=U"><h3>B</h3></a>
        <a href="https://example.com/c"><h3>C</h3></a>
    """
    adapter = GoogleSearchAdapter(SearchEngineConfig(), httpx.MockTransport(lambda _: httpx.Response(200, text=html)))
    result = await adapter.search("test", 2)
    assert [(hit.title, hit.url, hit.snippet) for hit in result.results] == [
        ("A", "https://example.com/a", ""),
        ("B", "https://example.com/b", ""),
    ]


@pytest.mark.asyncio
async def test_google_does_not_take_snippet_from_another_result():
    html = """
        <div id="search">
            <div><a href="https://example.com/a"><h3>A</h3></a></div>
            <div><a href="https://example.com/b"><h3>B</h3></a><div class="VwiC3b">B 摘要</div></div>
        </div>
    """
    adapter = GoogleSearchAdapter(SearchEngineConfig(), httpx.MockTransport(lambda _: httpx.Response(200, text=html)))
    result = await adapter.search("test", 5)
    assert [hit.snippet for hit in result.results] == ["", "B 摘要"]


@pytest.mark.asyncio
async def test_google_preserves_external_url_path():
    url = "https://example.com/url?q=article"
    adapter = GoogleSearchAdapter(
        SearchEngineConfig(),
        httpx.MockTransport(lambda _: httpx.Response(200, text=f'<a href="{url}"><h3>原始网址</h3></a>')),
    )
    assert (await adapter.search("test", 5)).results[0].url == url


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,html,message",
    [
        (429, "response-secret", "HTTP 429"),
        (200, '<form action="/sorry/index">response-secret</form>', "验证码"),
        (200, '<div class="g-recaptcha">response-secret</div>', "验证码"),
        (200, '<script src="https://google.com/recaptcha/api.js"></script>response-secret', "验证码"),
        (200, "<noscript>response-secret: enable JavaScript</noscript>", "JavaScript"),
    ],
)
async def test_google_failure_does_not_leak_response_or_retry(status, html, message):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, text=html)

    with pytest.raises(WebSearchError, match=message) as exc:
        await GoogleSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler)).search("test", 5)
    assert "response-secret" not in str(exc.value)
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("location", ["https://sorry.google.com/index", "https://www.google.com.hk/sorry/index"])
async def test_google_detects_captcha_redirect(location):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(302, headers={"Location": location})
        return httpx.Response(200, text="response-secret")

    with pytest.raises(WebSearchError, match="验证码") as exc:
        await GoogleSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler)).search("test", 5)
    assert "response-secret" not in str(exc.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("retry_succeeds", [True, False])
async def test_google_retries_opaque_redirect_once(retry_succeeds):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 2 and retry_succeeds:
            return httpx.Response(200, text='<a href="https://example.com"><h3>标题</h3></a>')
        return httpx.Response(200, text='<a href="/url?q=CAESopaque&amp;uoh=3"><h3>标题</h3></a>')

    adapter = GoogleSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler))
    if retry_succeeds:
        assert (await adapter.search("test", 5)).results[0].url == "https://example.com"
    else:
        with pytest.raises(WebSearchError, match="跳转链接"):
            await adapter.search("test", 5)
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,expected_count",
    [
        ('<a href="https://example.com"><h3>标题</h3></a>', 1),
        ('<div id="topstuff">Your search did not match any documents.</div>', 0),
        ('<div id="topstuff">找不到和您查询相符的内容</div>', 0),
    ],
)
async def test_google_query_echo_is_not_opaque_and_empty_results_are_success(body, expected_count):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, text="<title>q=CAESopaque uoh=3 - Google 搜索</title>" + body)

    result = await GoogleSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler)).search(
        "q=CAESopaque uoh=3", 5
    )
    assert len(result.results) == expected_count
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,message",
    [
        (httpx.ReadTimeout, "超时"),
        (httpx.ConnectError, "ConnectError"),
    ],
)
async def test_google_network_failure_is_safe(error, message):
    def handler(request: httpx.Request) -> httpx.Response:
        raise error("transport-secret", request=request)

    with pytest.raises(WebSearchError, match=message) as exc:
        await GoogleSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler)).search("test", 5)
    assert "transport-secret" not in str(exc.value)


@pytest.mark.asyncio
async def test_google_invalid_proxy_is_safe_before_network():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, text="")

    with pytest.raises(WebSearchError, match="代理") as exc:
        await GoogleSearchAdapter(
            SearchEngineConfig(proxy="ftp://user:proxy-secret@localhost:7890"),
            httpx.MockTransport(handler),
        ).search("test", 5)
    assert "proxy-secret" not in str(exc.value)
    assert not calls


@pytest.mark.asyncio
async def test_google_cancellation_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await GoogleSearchAdapter(SearchEngineConfig(), httpx.MockTransport(handler)).search("test", 5)
