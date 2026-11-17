from datetime import datetime
from typing import Dict, List, Optional, Set

import pytest

from src.chat.message_receive.message import SessionMessage
from src.common.data_models.mai_message_data_model import MessageInfo, UserInfo
from src.common.data_models.message_component_data_model import (
    AtComponent,
    DictComponent,
    EmojiComponent,
    ForwardComponent,
    ForwardNodeComponent,
    ImageComponent,
    MessageSequence,
    ReplyComponent,
    TextComponent,
    VoiceComponent,
)
from src.maisaka.context import history
from src.maisaka.context.messages import InternalContextMessage, LLMContextMessage, ToolResultMessage


@pytest.mark.parametrize("include_reply", [False, True])
@pytest.mark.parametrize("is_notify", [False, True])
@pytest.mark.parametrize("override_source", [False, True])
def test_visible_text_preserves_source_components(include_reply: bool, is_notify: bool, override_source: bool) -> None:
    nested_text = TextComponent("转发正文")
    node = ForwardComponent("转发用户", "forward-1", [nested_text])
    source = MessageSequence(
        [
            ReplyComponent(" reply-1 ", target_message_content="引用原文"),
            TextComponent("正文"),
            AtComponent("target", target_user_cardname="目标"),
            ImageComponent(binary_hash="image", content=" 图片描述 "),
            EmojiComponent(binary_hash="emoji"),
            VoiceComponent(binary_hash="voice", content=" 语音 "),
            ForwardNodeComponent([node]),
            DictComponent({"type": "custom", "data": [1, 2]}),
        ]
    )
    original_components = list(source.components)
    original_fields = [(component, vars(component).copy()) for component in [*source.components, node, nested_text]]
    message = SessionMessage("msg-1", datetime(2026, 11, 17, 12), "test")
    message.message_info = MessageInfo(UserInfo("user", "昵称", "群名片"))
    message.is_notify = is_notify
    message.raw_message = MessageSequence([TextComponent("原始消息")]) if override_source else source

    result = history.build_session_message_visible_text(
        message,
        source if override_source else None,
        include_reply_components=include_reply,
    )

    prefix = "12:00:00" + ("" if is_notify else "[msg_id:msg-1]") + "[群名片]"
    reply = "[引用消息]reply-1\n[发言内容]" if include_reply else ""
    assert result == prefix + reply + "正文@目标图片描述[表情包]语音"
    assert source.components == original_components
    assert all(vars(component) == fields for component, fields in original_fields)
    if override_source:
        assert message.raw_message.components[0].text == "原始消息"


def test_prefixed_message_sequence_keeps_source_independent() -> None:
    source = MessageSequence([TextComponent("正文"), ReplyComponent("reply-1")])

    result = history.build_prefixed_message_sequence(source, "前缀")

    assert len(result.components) == 1
    assert result.components[0].text == "前缀正文"
    assert result.components[0] is not source.components[0]
    assert source.components[0].text == "正文"
    assert len(source.components) == 2


def _build_history(turn_ids: List[Optional[str]]) -> List[LLMContextMessage]:
    timestamp = datetime(2026, 11, 17, 12)
    return [
        ToolResultMessage("结果", timestamp, f"call-{index}", turn_id)
        if turn_id is not None
        else InternalContextMessage(MessageSequence([TextComponent("用户上下文")]), "用户上下文", timestamp)
        for index, turn_id in enumerate(turn_ids)
    ]


@pytest.mark.parametrize(
    ("turn_ids", "selected", "expected"),
    [
        ([], {"turn-1"}, {}),
        (["turn-1", "turn-1", "turn-2"], {"turn-1", "turn-2"}, {}),
        ([None, "turn-1", "turn-1", None, "turn-1", "turn-2"], {"turn-1", "turn-2"}, {"turn-1": 0, "turn-2": 3}),
        ([None, "turn-1", None, "turn-2"], {"turn-2", "missing"}, {"turn-2": 2}),
        (["turn-1", None, "turn-1", "turn-2"], {"turn-1", "turn-2"}, {"turn-2": 1}),
        ([None, "turn-1"], set(), {}),
    ],
)
def test_tool_turn_anchors_keep_first_occurrence(
    turn_ids: List[Optional[str]],
    selected: Set[str],
    expected: Dict[str, int],
) -> None:
    messages = _build_history(turn_ids)
    original_selection = selected.copy()

    assert history.collect_tool_turn_anchor_indices(messages, selected) == expected
    assert selected == original_selection


@pytest.mark.parametrize("has_previous_user", [False, True])
def test_tool_turn_anchor_excludes_user_at_turn_start(monkeypatch, has_previous_user: bool) -> None:
    messages = _build_history([None, None, "turn-1"] if has_previous_user else [None, "turn-1"])
    turn_start = 1 if has_previous_user else 0
    monkeypatch.setattr(
        history,
        "_get_logical_turn_id",
        lambda message: "turn-1" if message is messages[turn_start] or message is messages[-1] else None,
    )

    expected = {"turn-1": 0} if has_previous_user else {}
    assert history.collect_tool_turn_anchor_indices(messages, {"turn-1"}) == expected
