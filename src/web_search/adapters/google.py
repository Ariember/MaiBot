"""Google 网页搜索，返回标题、原始链接和摘要。"""

from typing import List, Optional, Tuple
from urllib.parse import parse_qs, urlsplit
import asyncio

from bs4 import BeautifulSoup
import httpx

from src.common.http_client import get_shared_ssl_context_async

from ..config import SearchEngineConfig
from ..models import SearchHit, SearchResult, WebSearchError
from .http import MAX_RESPONSE_BYTES


GOOGLE_URL = "https://www.google.com.hk/search"
GOOGLE_HOSTS = (
    "google.com",
    "google.com.hk",
    "google.com.tw",
    "google.co.jp",
    "google.co.uk",
    "google.co.kr",
    "google.de",
    "google.fr",
    "googleusercontent.com",
)
SNIPPET_SELECTOR = ".ilUpNd.H66NU, .VwiC3b, .IsZvec, .aCOpRe, [data-sncf]"


class GoogleSearchAdapter:
    def __init__(self, config: SearchEngineConfig, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self.config = config
        self.transport = transport

    async def search(self, query: str, max_results: int) -> SearchResult:
        ssl_context = await get_shared_ssl_context_async()
        try:
            proxy = httpx.Proxy(self.config.proxy, ssl_context=ssl_context) if self.config.proxy else None
        except (ValueError, httpx.InvalidURL):
            raise WebSearchError("Google 搜索代理地址无效，请填写 HTTP(S) 或 SOCKS5 地址") from None
        try:
            async with httpx.AsyncClient(
                verify=ssl_context,
                proxy=proxy,
                transport=self.transport,
                timeout=self.config.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "Opera/9.80 (J2ME/MIDP; Opera Mini/8.0.35626/191.249; U; en) Presto/2.12.423 Version/12.16",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
                cookies={"CONSENT": "YES+"},
            ) as client:
                for attempt in range(2):
                    async with client.stream(
                        "GET",
                        GOOGLE_URL,
                        params={"q": query, "hl": "zh-CN", "client": "ms-opera-mini", "ie": "utf8", "filter": "0"},
                    ) as response:
                        if response.url.path.startswith("/sorry") or response.url.host == "sorry.google.com":
                            raise WebSearchError("Google 要求验证码，请稍后重试或切换联网搜索提供商")
                        if not response.is_success:
                            raise WebSearchError(f"Google 搜索返回 HTTP {response.status_code}")
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > MAX_RESPONSE_BYTES:
                                raise WebSearchError("Google 搜索响应超过 8 MiB 限制")
                    hits, opaque = await asyncio.to_thread(
                        self._parse, data.decode("utf-8", errors="replace"), max_results
                    )
                    # Google 的不透明跳转令牌无法取得原始网址，只在这一变体下重新请求一次。
                    if not hits and opaque:
                        if attempt == 0:
                            continue
                        raise WebSearchError("Google 返回了无法解析的跳转链接")
                    return SearchResult(query=query, results=hits)
        except httpx.TimeoutException:
            raise WebSearchError("Google 搜索请求超时") from None
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Google 搜索连接失败：{type(exc).__name__}") from None

    @staticmethod
    def _parse(html: str, max_results: int) -> Tuple[List[SearchHit], bool]:
        soup = BeautifulSoup(html, "html.parser")
        if soup.select_one('form[action*="/sorry"], .g-recaptcha, script[src*="recaptcha"]'):
            raise WebSearchError("Google 要求验证码，请稍后重试或切换联网搜索提供商")
        hits: List[SearchHit] = []
        seen = set()
        opaque = False
        for heading in soup.find_all("h3"):
            anchor = heading.find_parent("a", href=True)
            if anchor is None:
                continue
            url = str(anchor["href"])
            parsed = urlsplit(url)
            host = parsed.hostname or ""
            is_google = any(host == internal or host.endswith("." + internal) for internal in GOOGLE_HOSTS)
            if parsed.path == "/url" and (not host or is_google):
                params = parse_qs(parsed.query)
                url = (params.get("q") or params.get("url") or [""])[0]
                opaque = opaque or bool(url and not url.startswith(("http://", "https://")))
                parsed = urlsplit(url)
            host = parsed.hostname or ""
            title = heading.get_text(" ", strip=True)
            if not title or parsed.scheme not in ("http", "https") or not host or url in seen:
                continue
            if any(host == internal or host.endswith("." + internal) for internal in GOOGLE_HOSTS):
                continue
            snippet = ""
            # 摘要通常与标题分处卡片的两个子树，向上寻找而不固定整张卡片的 class。
            for container in anchor.find_parents("div", limit=4):
                if len(container.find_all("h3", limit=2)) > 1:
                    break
                node = container.select_one(SNIPPET_SELECTOR)
                if node is not None:
                    snippet = node.get_text(" ", strip=True)
                    break
            hits.append(SearchHit(title=title, url=url, snippet=snippet))
            seen.add(url)
            if len(hits) == max_results:
                break
        if not hits and not opaque:
            empty = soup.select_one("#topstuff")
            if empty is None or not any(
                marker in empty.get_text(" ", strip=True).lower()
                for marker in ("did not match any documents", "找不到和您查询", "没有找到", "未找到")
            ):
                raise WebSearchError("Google 未返回可解析的结果，页面可能要求 JavaScript 或已改变结构")
        return hits, opaque
