"""按描述从本地图库找图并发送。"""

from typing import Optional

import asyncio
import base64

from src.core.tooling import ToolExecutionContext, ToolExecutionResult, ToolInvocation, ToolSpec
from src.emoji_system.image_gallery import get_image_library, select_library_image
from src.services import send_service

from .context import BuiltinToolRuntimeContext


def get_tool_spec() -> ToolSpec:
    return ToolSpec(
        name="search_images",
        description="根据内容、人物、情绪或文字从本地图库寻找并发送图片或表情包。没有匹配时不会随机发图。",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "需要的图片内容、人物或情绪。"},
                "msg_id": {"type": "string", "description": "要回复的消息编号；小黑盒必须指定。"},
            },
            "required": ["query"],
        },
        provider_name="maisaka_builtin",
        provider_type="builtin",
    )


async def handle_tool(
    tool_ctx: BuiltinToolRuntimeContext,
    invocation: ToolInvocation,
    context: Optional[ToolExecutionContext] = None,
) -> ToolExecutionResult:
    query = str(invocation.arguments.get("query") or "").strip()
    if not query:
        return tool_ctx.build_failure_result(invocation.tool_name, "请提供图片描述。")
    target_id = str(invocation.arguments.get("msg_id") or "").strip()
    target = tool_ctx.runtime.find_source_message_by_id(target_id) if target_id else None
    if (target_id and target is None) or (tool_ctx.runtime.chat_stream.platform == "xiaoheihe" and target is None):
        return tool_ctx.build_failure_result(invocation.tool_name, "请指定可回复的消息编号 msg_id。")
    try:
        item = await select_library_image(query, session_id=tool_ctx.runtime.session_id)
        if item is None:
            return tool_ctx.build_failure_result(invocation.tool_name, "图库中没有找到符合描述的图片。")
        library = await asyncio.to_thread(get_image_library)
        data = await asyncio.to_thread(library.read_bytes, item["id"])
        sender = send_service.emoji_to_stream if "表情包" in item["tags"] else send_service.image_to_stream
        payload_key = "emoji_base64" if "表情包" in item["tags"] else "image_base64"
        sent = await sender(
            **{payload_key: base64.b64encode(data).decode("ascii")},
            stream_id=tool_ctx.runtime.session_id,
            reply_message=target,
            sync_to_maisaka_history=True,
            maisaka_source_kind="guided_reply",
        )
        if not sent:
            return tool_ctx.build_failure_result(invocation.tool_name, "图库图片发送失败。")
        return tool_ctx.build_success_result(
            invocation.tool_name, "已发送图库图片。", structured_content={"image_id": item["id"]}
        )
    except Exception as exc:
        return tool_ctx.build_failure_result(invocation.tool_name, f"图库图片发送失败：{type(exc).__name__}")
