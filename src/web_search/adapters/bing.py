"""Bing 网页搜索，返回原始网站链接和摘要。"""

from typing import List, Optional
from urllib.parse import parse_qs, urlsplit
import asyncio
import base64

from bs4 import BeautifulSoup
import httpx

from src.common.http_client import get_shared_ssl_context_async

from ..config import SearchEngineConfig
from ..models import SearchHit, SearchResult, WebSearchError
from .http import MAX_RESPONSE_BYTES


class BingSearchAdapter:
    def __init__(self, config: SearchEngineConfig, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self.config = config
        self.transport = transport

    async def search(self, query: str, max_results: int) -> SearchResult:
        ssl_context = await get_shared_ssl_context_async()
        try:
            proxy = httpx.Proxy(self.config.proxy, ssl_context=ssl_context) if self.config.proxy else None
        except (ValueError, httpx.InvalidURL):
            raise WebSearchError("Bing 搜索代理地址无效，请填写 HTTP(S) 或 SOCKS5 地址") from None
        try:
            async with httpx.AsyncClient(
                verify=ssl_context,
                proxy=proxy,
                transport=self.transport,
                timeout=self.config.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            ) as client:
                async with client.stream(
                    "GET", "https://www.bing.com/search", params={"q": query, "count": max_results}
                ) as response:
                    if response.url.path.startswith(("/turing/captcha", "/challenge")):
                        raise WebSearchError("Bing 要求验证码，请稍后重试或切换搜索引擎")
                    if not response.is_success:
                        raise WebSearchError(f"Bing 搜索返回 HTTP {response.status_code}")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_RESPONSE_BYTES:
                            raise WebSearchError("Bing 搜索响应超过 8 MiB 限制")
        except httpx.TimeoutException:
            raise WebSearchError("Bing 搜索请求超时") from None
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Bing 搜索连接失败：{type(exc).__name__}") from None
        hits = await asyncio.to_thread(self._parse, data.decode("utf-8", errors="replace"), max_results)
        return SearchResult(query=query, results=hits)

    @staticmethod
    def _parse(html: str, max_results: int) -> List[SearchHit]:
        soup = BeautifulSoup(html, "html.parser")
        if soup.select_one('#b_captcha, #b_captchaFrame, .g-recaptcha, iframe[src*="/captcha/"]'):
            raise WebSearchError("Bing 要求验证码，请稍后重试或切换搜索引擎")
        hits: List[SearchHit] = []
        seen = set()
        for item in soup.select("li.b_algo"):
            anchor = item.select_one("h2 a[href]")
            if anchor is None:
                continue
            title = anchor.get_text(" ", strip=True)
            url = str(anchor["href"])
            parsed = urlsplit(url)
            host = parsed.hostname or ""
            is_bing = host == "bing.com" or host.endswith(".bing.com")
            if parsed.path == "/ck/a" and (not host or is_bing):
                url = parse_qs(parsed.query).get("u", [""])[0]
                if url.startswith("a1"):
                    encoded = url[2:]
                    try:
                        url = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
                    except (ValueError, UnicodeError):
                        continue
                parsed = urlsplit(url)
            host = parsed.hostname or ""
            if not title or parsed.scheme not in ("http", "https") or not host or url in seen:
                continue
            if host == "bing.com" or host.endswith(".bing.com") or host == "bing.net" or host.endswith(".bing.net"):
                continue
            snippet = item.select_one(".b_caption p, .b_lineclamp2, .b_lineclamp3, .b_lineclamp4")
            hits.append(SearchHit(title=title, url=url, snippet=snippet.get_text(" ", strip=True) if snippet else ""))
            seen.add(url)
            if len(hits) == max_results:
                break
        if not hits and soup.select_one("#b_results .b_no") is None:
            raise WebSearchError("Bing 未返回可解析的结果，页面可能要求验证或已改变结构")
        return hits
