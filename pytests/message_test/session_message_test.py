import sys
import asyncio
import pytest
import importlib
import importlib.util
from threading import Event, get_ident
from types import ModuleType, SimpleNamespace
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from src.common.data_models.message_component_data_model import MessageSequence, ForwardComponent
    from src.chat.message_receive.message import (
        SessionMessage,
        TextComponent,
        ImageComponent,
        EmojiComponent,
        VoiceComponent,
        AtComponent,
        ReplyComponent,
        ForwardNodeComponent,
    )


class DummyLogger:
    def __init__(self) -> None:
        self.logging_record = []

    def debug(self, msg):
        print(f"DEBUG: {msg}")
        self.logging_record.append(f"DEBUG: {msg}")

    def info(self, msg):
        print(f"INFO: {msg}")
        self.logging_record.append(f"INFO: {msg}")

    def warning(self, msg):
        print(f"WARNING: {msg}")
        self.logging_record.append(f"WARNING: {msg}")

    def error(self, msg):
        print(f"ERROR: {msg}")
        self.logging_record.append(f"ERROR: {msg}")

    def critical(self, msg):
        print(f"CRITICAL: {msg}")
        self.logging_record.append(f"CRITICAL: {msg}")


def get_logger(name):
    return DummyLogger()


class DummyDBSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def exec(self, statement):
        return self

    def first(self):
        return None

    def commit(self):
        pass

    def all(self):
        return []


def get_db_session():
    return DummyDBSession()


def get_manual_db_session():
    return DummyDBSession()


class DummySelect:
    def __init__(self, model):
        self.model = model

    def filter_by(self, **kwargs):
        return self

    def where(self, condition):
        return self

    def limit(self, n):
        return self


def select(model):
    return DummySelect(model)


async def dummy_get_voice_text(binary_data):
    return None  # 可以根据需要返回模拟的文本结果


class DummyPersonUtils:
    @staticmethod
    def get_person_info_by_user_id_and_platform(user_id, platform):
        return None  # 可以根据需要返回模拟的用户信息


def setup_mocks(monkeypatch):
    def _stub_module(name: str) -> ModuleType:
        module = ModuleType(name)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    # src.common.logger
    logger_mod = _stub_module("src.common.logger")
    # Mock the logger
    logger_mod.get_logger = get_logger

    db_mod = _stub_module("src.common.database.database")
    db_mod.get_db_session = get_db_session
    db_mod.get_manual_db_session = get_manual_db_session

    db_model_mod = _stub_module("src.common.database.database_model")
    db_model_mod.Messages = None  # 可以根据需要添加更多的属性或方法

    emoji_manager_mod = _stub_module("src.emoji_system.emoji_manager")
    emoji_manager_mod.emoji_manager = None  # 可以根据需要添加更多的属性或方法

    image_manager_mod = _stub_module("src.chat.image_system.image_manager")
    image_manager_mod.image_manager = None  # 可以根据需要添加更多的属性或方法

    msg_utils_mod = _stub_module("src.common.utils.utils_message")
    msg_utils_mod.MessageUtils = None  # 可以根据需要添加更多的属性或方法

    voice_utils_mod = _stub_module("src.common.utils.utils_voice")
    voice_utils_mod.get_voice_text = dummy_get_voice_text

    person_utils_mod = _stub_module("src.common.utils.utils_person")
    person_utils_mod.PersonUtils = DummyPersonUtils


def load_message_via_file(monkeypatch):
    setup_mocks(monkeypatch)
    file_path = Path(__file__).parent.parent.parent / "src" / "chat" / "message_receive" / "message.py"
    spec = importlib.util.spec_from_file_location("message", file_path)
    message_module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "message_module", message_module)
    spec.loader.exec_module(message_module)
    message_module.select = select
    SessionMessageClass = message_module.SessionMessage
    TextComponentClass = message_module.TextComponent
    ImageComponentClass = message_module.ImageComponent
    EmojiComponentClass = message_module.EmojiComponent
    VoiceComponentClass = message_module.VoiceComponent
    AtComponentClass = message_module.AtComponent
    ReplyComponentClass = message_module.ReplyComponent
    ForwardNodeComponentClass = message_module.ForwardNodeComponent
    MessageSequenceClass = sys.modules["src.common.data_models.message_component_data_model"].MessageSequence
    ForwardComponentClass = sys.modules["src.common.data_models.message_component_data_model"].ForwardComponent
    globals()["SessionMessage"] = SessionMessageClass
    globals()["TextComponent"] = TextComponentClass
    globals()["ImageComponent"] = ImageComponentClass
    globals()["EmojiComponent"] = EmojiComponentClass
    globals()["VoiceComponent"] = VoiceComponentClass
    globals()["AtComponent"] = AtComponentClass
    globals()["ReplyComponent"] = ReplyComponentClass
    globals()["ForwardNodeComponent"] = ForwardNodeComponentClass
    globals()["MessageSequence"] = MessageSequenceClass
    globals()["ForwardComponent"] = ForwardComponentClass
    return message_module


@pytest.mark.asyncio
async def test_image_save_failure_preserves_original_bytes(monkeypatch):
    module = load_message_via_file(monkeypatch)
    manager_module = sys.modules["src.chat.image_system.image_manager"]
    manager = ModuleType("test_image_manager")
    manager.get_image_description = AsyncMock(side_effect=OSError("磁盘写入失败"))
    monkeypatch.setattr(manager_module, "image_manager", manager)
    component = module.ImageComponent(binary_hash="", binary_data=b"original-image")

    with pytest.raises(OSError, match="磁盘写入失败"):
        await module.SessionMessage.process_image_component(None, component)

    assert component.binary_data == b"original-image"
    assert component.content == ""


@pytest.mark.asyncio
async def test_process(monkeypatch):
    load_message_via_file(monkeypatch)
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [TextComponent("Hello, world!")]
    await msg.process()
    assert msg.processed_plain_text == "Hello, world!"


@pytest.mark.asyncio
async def test_multiple_text(monkeypatch):
    load_message_via_file(monkeypatch)
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [TextComponent("Hello,"), TextComponent("world!")]
    await msg.process()
    assert msg.processed_plain_text == "Hello, world!"


@pytest.mark.asyncio
async def test_image(monkeypatch):
    load_message_via_file(monkeypatch)
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [ImageComponent(binary_hash="image_hash"), TextComponent("Hello, world!")]
    await msg.process()
    assert msg.processed_plain_text == "[一张图片，网卡了加载不出来] Hello, world!"


@pytest.mark.asyncio
async def test_emoji(monkeypatch):
    load_message_via_file(monkeypatch)
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [EmojiComponent(binary_hash="emoji_hash"), TextComponent("Hello, world!")]
    await msg.process()
    assert msg.processed_plain_text == "[一个表情，网卡了加载不出来] Hello, world!"


@pytest.mark.asyncio
async def test_voice(monkeypatch):
    load_message_via_file(monkeypatch)
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [VoiceComponent(binary_hash="voice_hash"), TextComponent("Hello, world!")]
    await msg.process()
    assert msg.processed_plain_text == "[语音消息，转录失败] Hello, world!"


@pytest.mark.asyncio
async def test_at_component(at_message_module):
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.platform = "test_platform"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [AtComponent(target_user_id="114514"), TextComponent("Hello, world!")]
    await msg.process()
    assert msg.processed_plain_text == "@114514 Hello, world!"


@pytest.fixture
def at_message_module(monkeypatch):
    module = load_message_via_file(monkeypatch)
    config = ModuleType("src.config.config")
    config.global_config = SimpleNamespace(bot=SimpleNamespace(nickname=" 小麦 "))
    monkeypatch.setitem(sys.modules, config.__name__, config)
    system_utils = ModuleType("src.common.utils.system_utils")
    system_utils.is_bot_self = lambda platform, user_id: user_id == "bot"
    monkeypatch.setitem(sys.modules, system_utils.__name__, system_utils)
    return module


def make_at_message(module, components, platform="instance-qq", group_id="group1"):
    msg = module.SessionMessage("msg123", datetime.now(), platform=platform)
    msg.message_info = SimpleNamespace(group_info=SimpleNamespace(group_id=group_id))
    msg.raw_message = MessageSequence(components=components)
    return msg


@pytest.mark.asyncio
async def test_at_queries_share_pending_work_off_event_loop(monkeypatch, at_message_module):
    module = at_message_module
    loop = asyncio.get_running_loop()
    loop_thread = get_ident()
    entered = asyncio.Event()
    release = Event()
    calls = []

    def lookup(user_id, platform):
        assert get_ident() != loop_thread
        calls.append((platform, user_id))
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        return SimpleNamespace(
            user_nickname=f"昵称{user_id}",
            group_cardname_list=[
                SimpleNamespace(group_id="other", group_cardname="别群名片"),
                SimpleNamespace(group_id="group1", group_cardname=f"名片{user_id}"),
            ],
        )

    monkeypatch.setattr(DummyPersonUtils, "get_person_info_by_user_id_and_platform", staticmethod(lookup))
    components = [module.AtComponent(user_id) for user_id in ("1", "1", "2", "1")]
    msg = make_at_message(module, components)
    processing = asyncio.create_task(msg.process())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        assert not processing.done()
    finally:
        release.set()
        await processing

    assert sorted(calls) == [("instance-qq", "1"), ("instance-qq", "2")]
    assert msg.processed_plain_text == "@名片1 @名片1 @名片2 @名片1"
    assert [(item.target_user_nickname, item.target_user_cardname) for item in components] == [
        ("昵称1", "名片1"), ("昵称1", "名片1"), ("昵称2", "名片2"), ("昵称1", "名片1"),
    ]


@pytest.mark.asyncio
async def test_at_missing_person_cache_spans_nested_forwards_and_resets(monkeypatch, at_message_module):
    module = at_message_module
    calls = []

    def lookup(user_id, platform):
        calls.append((platform, user_id))
        return None

    monkeypatch.setattr(DummyPersonUtils, "get_person_info_by_user_id_and_platform", staticmethod(lookup))
    inner_at = module.AtComponent("missing")
    nested = module.ForwardNodeComponent([
        ForwardComponent("内层", "inner", [inner_at]),
    ])
    forwarded = module.ForwardNodeComponent([
        ForwardComponent("外层", "outer", [module.AtComponent("missing"), nested]),
    ])
    msg = make_at_message(module, [module.AtComponent("missing"), forwarded])
    await msg.process()

    assert calls == [("instance-qq", "missing")]
    assert msg.processed_plain_text == (
        "@missing 【合并转发消息: \n"
        "-- 【外层】: @missing 【合并转发消息: \n"
        "------ 【内层】: @missing\n】\n】"
    )
    assert inner_at.target_user_nickname is None
    assert inner_at.target_user_cardname is None
    await msg.process()
    assert calls == [("instance-qq", "missing"), ("instance-qq", "missing")]


@pytest.mark.asyncio
async def test_at_component_and_bot_names_keep_precedence(monkeypatch, at_message_module):
    module = at_message_module

    def lookup(user_id, platform):
        pytest.fail("已有名字及机器人昵称不应查询人物信息")

    monkeypatch.setattr(DummyPersonUtils, "get_person_info_by_user_id_and_platform", staticmethod(lookup))
    components = [
        module.AtComponent("1", "昵称", "名片甲"),
        module.AtComponent("1", "昵称", "名片乙"),
        module.AtComponent("1", "昵称"),
        module.AtComponent("bot", "平台昵称"),
        module.AtComponent("bot"),
    ]
    msg = make_at_message(module, components)
    await msg.process()

    assert msg.processed_plain_text == "@名片甲 @名片乙 @昵称 @平台昵称 @小麦"
    assert [(item.target_user_nickname, item.target_user_cardname, item.uses_configured_bot_nickname)
            for item in components] == [
        ("昵称", "名片甲", False), ("昵称", "名片乙", False), ("昵称", None, False),
        ("平台昵称", None, False), ("小麦", "小麦", True),
    ]


@pytest.mark.asyncio
async def test_at_cache_normalizes_platform_and_preserves_group_names(monkeypatch, at_message_module):
    module = at_message_module
    calls = []

    def lookup(user_id, platform):
        calls.append((platform, user_id))
        return SimpleNamespace(
            user_nickname=platform,
            group_cardname_list=[SimpleNamespace(group_id="group1", group_cardname="群一名片")],
        )

    monkeypatch.setattr(DummyPersonUtils, "get_person_info_by_user_id_and_platform", staticmethod(lookup))
    mapping = module.MsgIDMapping()
    first = make_at_message(module, [], platform="a-qq")
    alias = make_at_message(module, [], platform="b-qq", group_id="group2")
    other = make_at_message(module, [], platform="discord", group_id="group2")
    components = [module.AtComponent("1") for _ in range(3)]
    result = await asyncio.gather(*[
        msg.process_at_component(component, mapping)
        for msg, component in zip((first, alias, other), components, strict=True)
    ])

    assert sorted(calls) == [("a-qq", "1"), ("discord", "1")]
    assert result == ["@群一名片", "@a-qq", "@discord"]
    assert [item.target_user_cardname for item in components] == ["群一名片", None, None]


@pytest.mark.asyncio
async def test_at_lookup_exception_keeps_component_error_handling(monkeypatch, at_message_module):
    module = at_message_module
    calls = []

    def lookup(user_id, platform):
        calls.append((platform, user_id))
        raise RuntimeError("人物查询失败")

    monkeypatch.setattr(DummyPersonUtils, "get_person_info_by_user_id_and_platform", staticmethod(lookup))
    msg = make_at_message(module, [module.AtComponent("1"), module.AtComponent("1"), module.TextComponent("正文")])
    await msg.process()

    assert calls == [("instance-qq", "1")]
    assert msg.processed_plain_text == "正文"
    assert sum("人物查询失败" in entry for entry in module.logger.logging_record) == 2
    with pytest.raises(RuntimeError, match="人物查询失败"):
        await msg.process_at_component(module.AtComponent("1"))


@pytest.mark.asyncio
async def test_reply_component_fail_to_fetch(monkeypatch):
    load_message_via_file(monkeypatch)
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.platform = "test_platform"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [ReplyComponent(target_message_id="1919810"), TextComponent("Hello, world!")]
    await msg.process()
    assert msg.processed_plain_text == "[回复了一条消息，但原消息已无法访问] Hello, world!"


@pytest.mark.asyncio
async def test_reply_component_success(monkeypatch):
    module_msg = load_message_via_file(monkeypatch)

    class DummyDBSessionWithReply(DummyDBSession):
        def exec(self, s):
            return self

        def first(inner_self):
            class DummyRecord:
                processed_plain_text = "原消息内容"
                user_cardname = "cardname123"
                user_nickname = "nickname123"
                user_id = "userid123"

            return DummyRecord()

    module_msg.get_db_session = lambda: DummyDBSessionWithReply()
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.platform = "test_platform"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [ReplyComponent(target_message_id="1919810"), TextComponent("Hello, world!")]
    await msg.process()
    assert msg.processed_plain_text == "[回复了cardname123的消息: 原消息内容] Hello, world!"


@pytest.mark.asyncio
async def test_reply_component_with_db_fail(monkeypatch):
    module_msg = load_message_via_file(monkeypatch)

    class DummyDBSessionWithError(DummyDBSession):
        def exec(self, s):
            raise Exception("数据库查询失败")

    module_msg.get_db_session = lambda: DummyDBSessionWithError()
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.platform = "test_platform"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [ReplyComponent(target_message_id="1919810"), TextComponent("Hello, world!")]
    await msg.process()
    assert msg.processed_plain_text == "[回复了一条消息，但原消息已无法访问] Hello, world!"
    assert any("数据库查询失败" in log for log in module_msg.logger.logging_record)


@pytest.mark.asyncio
async def test_forward_component(monkeypatch):
    load_message_via_file(monkeypatch)
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.platform = "test_platform"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [
        ForwardNodeComponent(
            forward_components=[
                ForwardComponent(
                    message_id="msg1",
                    user_id="user1",
                    user_nickname="nickname1",
                    user_cardname="cardname1",
                    content=[TextComponent("转发消息1")],
                ),
                ForwardComponent(
                    message_id="msg2",
                    user_id="user2",
                    user_nickname="nickname2",
                    user_cardname="cardname2",
                    content=[TextComponent("转发消息2")],
                ),
            ]
        ),
        TextComponent("Hello, world!"),
    ]
    await msg.process()
    print("Processed plain text:", msg.processed_plain_text)
    expected_forward_text = """【合并转发消息: 
-- 【cardname1】: 转发消息1
-- 【cardname2】: 转发消息2
】 Hello, world!"""
    assert msg.processed_plain_text == expected_forward_text


@pytest.mark.asyncio
async def test_forward_with_reply(monkeypatch):
    load_message_via_file(monkeypatch)
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.platform = "test_platform"
    msg.raw_message = MessageSequence(components=[])
    msg.raw_message.components = [
        ForwardNodeComponent(
            forward_components=[
                ForwardComponent(
                    message_id="msg1",
                    user_id="user1",
                    user_nickname="nickname1",
                    user_cardname="cardname1",
                    content=[TextComponent("转发消息1")],
                ),
                ForwardComponent(
                    message_id="msg2",
                    user_id="user2",
                    user_nickname="nickname2",
                    user_cardname="cardname2",
                    content=[ReplyComponent(target_message_id="msg1"), TextComponent("转发消息2")],
                ),
            ]
        ),
        TextComponent("Hello, world!"),
    ]
    await msg.process()
    assert (
        msg.processed_plain_text
        == """【合并转发消息: 
-- 【cardname1】: 转发消息1
-- 【cardname2】: [回复了cardname1的消息: 转发消息1] 转发消息2
】 Hello, world!"""
    )


@pytest.mark.asyncio
async def test_multiple_reply_with_delay_in_forward(monkeypatch):
    load_message_via_file(monkeypatch)
    msg = SessionMessage("msg123", datetime.now(), platform="test_platform")
    msg.session_id = "session123"
    msg.platform = "test_platform"
    msg.raw_message = MessageSequence(components=[])

    async def delayed_get_voice_text(binary_data):
        await asyncio.sleep(0.5)  # 模拟延迟
        return "这是语音转文本的结果"

    sys.modules["src.common.utils.utils_voice"].get_voice_text = delayed_get_voice_text

    msg.raw_message.components = [
        ForwardNodeComponent(
            forward_components=[
                ForwardComponent(
                    message_id="msg1",
                    user_id="user1",
                    user_nickname="nickname1",
                    user_cardname="cardname1",
                    content=[VoiceComponent(binary_hash="voice_hash1"), TextComponent("转发消息1")],
                ),
                ForwardComponent(
                    message_id="msg2",
                    user_id="user2",
                    user_nickname="nickname2",
                    user_cardname="cardname2",
                    content=[ReplyComponent(target_message_id="msg1"), TextComponent("转发消息2")],
                ),
                ForwardComponent(
                    message_id="msg3",
                    user_id="user3",
                    user_nickname="nickname3",
                    user_cardname="cardname3",
                    content=[ReplyComponent(target_message_id="msg1"), TextComponent("转发消息3")],
                ),
            ]
        ),
    ]
    await msg.process()
    expected_text = """【合并转发消息: 
-- 【cardname1】: [语音: 这是语音转文本的结果] 转发消息1
-- 【cardname2】: [回复了cardname1的消息: [语音: 这是语音转文本的结果] 转发消息1] 转发消息2
-- 【cardname3】: [回复了cardname1的消息: [语音: 这是语音转文本的结果] 转发消息1] 转发消息3
】"""
    assert msg.processed_plain_text == expected_text
