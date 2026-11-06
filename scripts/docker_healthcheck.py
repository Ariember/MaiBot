"""检查容器内 WebUI 可响应；不读取或输出访问令牌。"""

from urllib.request import urlopen
import json

from src.config.startup_bindings import get_local_http_base_url


def main() -> None:
    with urlopen(f"{get_local_http_base_url()}/api/webui/health", timeout=3) as response:
        if response.status != 200 or json.load(response).get("status") != "healthy":
            raise RuntimeError("WebUI 健康检查未通过")


if __name__ == "__main__":
    main()
