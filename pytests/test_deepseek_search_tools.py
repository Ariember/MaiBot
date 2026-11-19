from httpx import AsyncClient, MockTransport, Request, Response

import json
import pytest

from src.config.model_configs import APIProvider, ModelInfo
from src.llm_models.model_client import openai_client
from src.llm_models.model_client.base_client import ResponseRequest
from src.llm_models.payload_content.context_item import ContextItemMeta, ContextTextPart, UserMessageItem
from src.llm_models.payload_content.tool_option import ToolOption


@pytest.mark.asyncio
@pytest.mark.parametrize("nested", [False, True])
async def test_chat_sends_deepseek_search_alongside_function_tools(monkeypatch, nested: bool) -> None:
    def handle_request(request: Request) -> Response:
        function, search = json.loads(request.content)["tools"]
        assert function["function"]["name"] == "lookup"
        assert search == {"type": "deepseek_web_search"}
        return Response(
            200,
            json={
                "id": "test",
                "created": 0,
                "model": "deepseek-flash",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            },
        )

    async with AsyncClient(transport=MockTransport(handle_request)) as http_client:
        monkeypatch.setattr(openai_client, "DefaultAsyncHttpxClient", lambda **kwargs: http_client)
        provider = APIProvider(name="test", base_url="https://api.deepseek.com", api_key="test")
        client = openai_client.OpenaiClient(provider)
        tools = {"tools": [{"type": "deepseek_web_search"}]}
        request = ResponseRequest(
            model_info=ModelInfo(
                name="flash", model_type="llm", model_identifier="deepseek-flash", api_provider="test",
                force_stream_mode=False,
            ),
            context_items=[UserMessageItem(meta=ContextItemMeta.create(), parts=(ContextTextPart("查询"),))],
            tool_options=[ToolOption(name="lookup", description="查询")],
            extra_params={"body": tools} if nested else tools,
        )
        await client.get_response(request)
